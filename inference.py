import os
import json
import time
import logging
import io
import base64
from typing import Dict, Any, Tuple, Union

import torch
import torchvision
import numpy as np
import pandas as pd
import boto3
import pydicom

from sagemaker_inference import content_types, errors, model_server
from sagemaker_inference.default_inference_handler import DefaultInferenceHandler

try:
    import sys
    if '/workspace/EchoPrime' not in sys.path:
         sys.path.insert(0, '/workspace/EchoPrime')
    import utils
    import video_utils
except ImportError:
    logger.error("Failed to import local 'utils' or 'video_utils'. Ensure they are in the container and WORKDIR is correct.")
    utils = None
    video_utils = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DICOM_MIME_TYPE = "application/dicom"
MODEL_VERSION = "EchoPrime v1.0"

s3_client = boto3.client('s3')

class EchoPrimeHandler(DefaultInferenceHandler):

    def default_model_fn(self, model_dir: str) -> Dict[str, Any]:

        logger.info(f"Loading EchoPrime components from {model_dir}...")
        start_time = time.time()

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {device}")

        try:
            logger.info("Loading EchoPrime encoder...")
            encoder_path = os.path.join(model_dir, "weights", "echo_prime_encoder.pt")
            if not os.path.exists(encoder_path):
                raise FileNotFoundError(f"Encoder weights not found: {encoder_path}")
            echo_encoder = torchvision.models.video.mvit_v2_s()
            echo_encoder.head[-1] = torch.nn.Linear(echo_encoder.head[-1].in_features, 512)
            checkpoint = torch.load(encoder_path, map_location=device)
            echo_encoder.load_state_dict(checkpoint)
            echo_encoder.eval()
            echo_encoder.to(device)
            for param in echo_encoder.parameters(): param.requires_grad = False
            logger.info("EchoPrime encoder loaded.")

            logger.info("Loading View classifier...")
            vc_path = os.path.join(model_dir, "weights", "view_classifier.ckpt")
            if not os.path.exists(vc_path):
                raise FileNotFoundError(f"View classifier weights not found: {vc_path}")
            view_classifier = torchvision.models.convnext_base()
            view_classifier.classifier[-1] = torch.nn.Linear(view_classifier.classifier[-1].in_features, 11)
            vc_checkpoint = torch.load(vc_path, map_location=device)
            vc_state_dict = {k.replace("model.", "", 1).replace("module.", "", 1): v for k, v in vc_checkpoint.get("state_dict", vc_checkpoint).items()}
            view_classifier.load_state_dict(vc_state_dict)
            view_classifier.eval()
            view_classifier.to(device)
            for param in view_classifier.parameters(): param.requires_grad = False
            logger.info("View classifier loaded.")

            logger.info("Loading auxiliary data...")
            mil_weights_path = os.path.join(model_dir, "MIL_weights.csv")
            candidates_csv_path = os.path.join(model_dir, "candidates_data", "candidate_studies.csv")
            cand_emb_p1_path = os.path.join(model_dir, "candidates_data", "candidate_embeddings_p1.pt")
            cand_emb_p2_path = os.path.join(model_dir, "candidates_data", "candidate_embeddings_p2.pt")
            cand_reports_path = os.path.join(model_dir, "candidates_data", "candidate_reports.pkl")
            cand_labels_path = os.path.join(model_dir, "candidates_data", "candidate_labels.pkl")
            sec_pheno_path = os.path.join(model_dir, "section_to_phenotypes.pkl")

            required_files = [
                mil_weights_path, candidates_csv_path, cand_emb_p1_path, cand_emb_p2_path,
                cand_reports_path, cand_labels_path, sec_pheno_path
            ]
            for f_path in required_files:
                if not os.path.exists(f_path):
                    raise FileNotFoundError(f"Auxiliary file not found: {f_path}")

            mil_weights_df = pd.read_csv(mil_weights_path)
            non_empty_sections = mil_weights_df["Section"].tolist()
            section_weights = mil_weights_df.iloc[:, 1:].to_numpy()

            candidate_studies = pd.read_csv(candidates_csv_path)["Study"].tolist()
            map_location = 'cpu' if device.type == 'cpu' else device
            candidate_embeddings_p1 = torch.load(cand_emb_p1_path, map_location=map_location)
            candidate_embeddings_p2 = torch.load(cand_emb_p2_path, map_location=map_location)
            candidate_embeddings = torch.cat(
                (candidate_embeddings_p1, candidate_embeddings_p2),
                dim=0
            ).to(device)
            # candidate_embeddings = torch.nn.functional.normalize(candidate_embeddings, dim=1) # Optional normalization

            candidate_reports_raw = pd.read_pickle(cand_reports_path)
            if utils:
                 candidate_reports = [utils.phrase_decode(vec_phr) for vec_phr in candidate_reports_raw]
            else:
                 logger.warning("utils not imported, cannot decode candidate reports.")
                 candidate_reports = []

            candidate_labels = pd.read_pickle(cand_labels_path)
            section_to_phenotypes = pd.read_pickle(sec_pheno_path)
            logger.info("Auxiliary data loaded.")

            load_time = time.time() - start_time
            logger.info(f"All components loaded successfully in {load_time:.2f} seconds")

            return {
                "echo_encoder": echo_encoder,
                "view_classifier": view_classifier,
                "device": device,
                "mil_weights": section_weights,
                "non_empty_sections": non_empty_sections,
                "candidate_studies": candidate_studies,
                "candidate_embeddings": candidate_embeddings,
                "candidate_reports": candidate_reports,
                "candidate_labels": candidate_labels,
                "section_to_phenotypes": section_to_phenotypes,
                "utils": utils, # Pass utils module if needed later
                "video_utils": video_utils # Pass video_utils module if needed later
            }

        except Exception as e:
            logger.exception(f"Error loading models or auxiliary data: {str(e)}")
            raise

    def default_input_fn(self,
                        input_data: Union[str, bytes],
                        content_type: str) -> Dict[str, Any]:
        logger.info(f"Processing input with content type: {content_type}")
        if content_type == content_types.JSON:
            try:
                payload = json.loads(input_data)
                if "s3_uri" in payload:
                    logger.info(f"Processing S3 URI: {payload['s3_uri']}")
                    s3_parts = payload["s3_uri"].replace("s3://", "").split("/", 1)
                    bucket, key = s3_parts[0], s3_parts[1]
                    if not key.lower().endswith(".dcm"):
                        raise errors.UnsupportedFormatError(f"Unsupported file type: {key}. Expects DICOM (.dcm).")
                    try:
                        response = s3_client.get_object(Bucket=bucket, Key=key)
                        dicom_content = response["Body"].read()
                        return {"dicom_dataset": pydicom.dcmread(io.BytesIO(dicom_content))}
                    except Exception as e:
                        logger.exception(f"Error fetching from S3: {str(e)}")
                        raise errors.InternalServerError(f"S3 fetch failed: {str(e)}")
                elif "base64" in payload and payload.get("content_type") == DICOM_MIME_TYPE:
                    logger.info("Processing base64 encoded DICOM data")
                    dicom_content = base64.b64decode(payload["base64"])
                    return {"dicom_dataset": pydicom.dcmread(io.BytesIO(dicom_content))}
                else:
                    raise errors.UnsupportedFormatError("Unrecognized JSON payload format.")
            except json.JSONDecodeError as e:
                raise errors.BadRequestError(f"Invalid JSON payload: {str(e)}")
            except Exception as e:
                 logger.exception(f"Error processing JSON input: {e}")
                 raise errors.BadRequestError(f"Could not process JSON input: {e}")
        elif content_type == DICOM_MIME_TYPE:
            logger.info(f"Processing DICOM data ({len(input_data)} bytes)")
            try:
                return {"dicom_dataset": pydicom.dcmread(io.BytesIO(input_data))}
            except Exception as e:
                logger.exception(f"Error parsing DICOM data: {str(e)}")
                raise errors.BadRequestError(f"Error parsing DICOM data: {str(e)}")
        else:
            raise errors.UnsupportedFormatError(f"Unsupported content type: {content_type}.")

    def default_predict_fn(self, data: Dict[str, Any],
                          model_dict: Dict[str, Any]) -> Dict[str, Any]:
        
        logger.info("Starting prediction...")
        start_time = time.time()
        try:
            echo_encoder = model_dict["echo_encoder"]
            view_classifier = model_dict["view_classifier"]
            device = model_dict["device"]
            section_weights = model_dict["mil_weights"]
            non_empty_sections = model_dict["non_empty_sections"]
            candidate_studies = model_dict["candidate_studies"]
            candidate_embeddings = model_dict["candidate_embeddings"]
            candidate_reports = model_dict["candidate_reports"]
            candidate_labels = model_dict["candidate_labels"]
            section_to_phenotypes = model_dict["section_to_phenotypes"]
            utils = model_dict["utils"]
            video_utils = model_dict["video_utils"]

            if not utils or not video_utils:
                 raise RuntimeError("Missing 'utils' or 'video_utils' modules. Cannot proceed.")

            dicom_dataset = data["dicom_dataset"]

            logger.info("Preprocessing DICOM...")
            try:
                pixels = dicom_dataset.pixel_array
                original_pixels_for_masking = dicom_dataset.pixel_array

                if pixels.ndim < 3 or (pixels.ndim == 3 and pixels.shape[-1] != 3):
                     if pixels.ndim == 2: pixels = np.repeat(pixels[..., None], 3, axis=2)[None, ...]
                     elif pixels.ndim == 3 and pixels.shape[-1] != 3: pixels = np.repeat(pixels[..., None], 3, axis=-1)
                     else: raise ValueError(f"Unsupported pixel array shape: {pixels.shape}")
                elif pixels.ndim == 3 and pixels.shape[-1] == 3: pixels = pixels[None, ...]
                if pixels.ndim != 4: raise ValueError(f"Expected 4D pixel array (T, H, W, C), got {pixels.ndim}D")

                masked_pixels = video_utils.mask_outside_ultrasound(original_pixels_for_masking)
                if masked_pixels.ndim == 3:
                    masked_pixels = np.repeat(masked_pixels[..., None], 3, axis=-1)
                elif masked_pixels.ndim == 2:
                    masked_pixels = np.repeat(masked_pixels[..., None], 3, axis=2)[None, ...]

                frames_to_take = 32
                frame_stride = 2
                video_size = 224
                mean = torch.tensor([29.110628, 28.076836, 29.096405], device=device).reshape(3, 1, 1, 1)
                std = torch.tensor([47.989223, 46.456997, 47.20083], device=device).reshape(3, 1, 1, 1)

                num_frames = masked_pixels.shape[0]
                processed_video = np.zeros((num_frames, video_size, video_size, 3), dtype=np.float32)
                for i in range(num_frames):
                    frame_to_process = masked_pixels[i]
                    if frame_to_process.ndim == 2:
                         frame_to_process = np.repeat(frame_to_process[..., None], 3, axis=2)
                    processed_video[i] = video_utils.crop_and_scale(frame_to_process)

                x = torch.as_tensor(processed_video, dtype=torch.float32, device=device).permute([3, 0, 1, 2]) # C, T, H, W
                x.sub_(mean).div_(std)

                current_frames = x.shape[1]
                indices = torch.arange(0, min(current_frames, frames_to_take * frame_stride), frame_stride, device=device)
                if len(indices) > frames_to_take: indices = indices[:frames_to_take]
                x_selected = x[:, indices, :, :]

                if x_selected.shape[1] < frames_to_take:
                    padding = torch.zeros((3, frames_to_take - x_selected.shape[1], video_size, video_size), dtype=torch.float, device=device)
                    x_selected = torch.cat((x_selected, padding), dim=1)

                video_tensor = x_selected.unsqueeze(0)
                logger.info("DICOM preprocessing complete.")

            except Exception as e:
                logger.exception("Error during DICOM preprocessing")
                raise errors.BadRequestError(f"Failed to preprocess DICOM: {e}")

            logger.info("Encoding study...")
            with torch.no_grad():
                video_features = echo_encoder(video_tensor)

                first_frame_tensor = video_tensor[:, :, 0, :, :].to(device) # Shape: (1, C, H, W)
                view_logits = view_classifier(first_frame_tensor) # Shape: (1, 11)
                view_index = torch.argmax(view_logits, dim=1) # Shape: (1,)
                view_encoding = torch.nn.functional.one_hot(view_index, num_classes=11).float().to(device) # Shape: (1, 11)

            # Combine features and view encoding for the single video
            encoded_study = torch.cat((video_features, view_encoding), dim=1) # Shape: (1, 512 + 11)
            logger.info("Study encoding complete.")

            # --- 3. Generate Report (Adapt generate_report logic) ---
            logger.info("Generating report...")
            generated_report = ""
            encoded_study_cpu = encoded_study.cpu() # Move to CPU for report/metrics
            try:
                for s_dx, sec in enumerate(non_empty_sections):
                    # Weighting based on the single view detected
                    view_idx_item = view_index.item() # Get the single view index
                    # Ensure view_idx_item is within bounds for section_weights
                    if view_idx_item >= section_weights.shape[1]:
                         logger.warning(f"View index {view_idx_item} out of bounds for section weights (max: {section_weights.shape[1]-1}). Skipping section '{sec}'.")
                         continue
                    current_weight = section_weights[s_dx][view_idx_item]


                    # Apply weight to video features
                    no_view_study_embedding = encoded_study_cpu[0, :512] * current_weight # Shape: (512,)

                    # Normalize and calculate similarities
                    norm_val = torch.linalg.norm(no_view_study_embedding)
                    if norm_val > 1e-6: # Avoid division by zero
                         no_view_study_embedding = no_view_study_embedding / norm_val
                    else:
                         logger.warning(f"Zero vector for section '{sec}', skipping similarity.")
                         continue # Skip if embedding is zero

                    # Ensure candidate embeddings are on CPU
                    similarities = no_view_study_embedding @ candidate_embeddings.cpu().T # Shape: (num_candidates,)

                    # Find best matching candidate report section
                    extracted_section = "Section not found."
                    # Sort similarities to find best matches robustly
                    sorted_indices = torch.argsort(similarities, descending=True)
                    for max_id_tensor in sorted_indices:
                         max_id = max_id_tensor.item() # Convert tensor index to int
                         if max_id >= len(candidate_reports): continue # Safety check
                         predicted_section = candidate_reports[max_id]
                         extracted_section = utils.extract_section(predicted_section, sec)
                         if extracted_section != "Section not found.":
                              generated_report += extracted_section
                              break # Found a match for this section
                    if extracted_section == "Section not found.":
                         logger.warning(f"No matching candidate report found for section: {sec}")

                logger.info("Report generation complete.")
            except Exception as e:
                 logger.exception("Error during report generation")
                 generated_report = "Error generating report." # Provide fallback

            # --- 4. Predict Metrics (Adapt predict_metrics logic) ---
            logger.info("Predicting metrics...")
            preds = {}
            try:
                k = 50 # Top k candidates
                # Calculate per-section embedding (only 1 video, so slightly different)
                per_section_study_embedding = torch.zeros(len(non_empty_sections), 512)
                view_idx_item = view_index.item() # Get the single view index
                for s_dx, sec in enumerate(non_empty_sections):
                    # Ensure view_idx_item is within bounds for section_weights
                    if view_idx_item >= section_weights.shape[1]:
                         logger.warning(f"View index {view_idx_item} out of bounds for section weights (max: {section_weights.shape[1]-1}) during metrics prediction for section '{sec}'.")
                         # Handle this case, e.g., skip or use zero weights
                         continue
                    current_weight = section_weights[s_dx][view_idx_item]
                    per_section_study_embedding[s_dx] = encoded_study_cpu[0, :512] * current_weight


                # Normalize per-section embeddings
                norms = torch.linalg.norm(per_section_study_embedding, dim=1, keepdim=True)
                safe_norms = torch.where(norms > 1e-6, norms, torch.tensor(1.0)) # Avoid division by zero
                per_section_study_embedding_norm = per_section_study_embedding / safe_norms

                # Calculate similarities
                similarities = per_section_study_embedding_norm @ candidate_embeddings.cpu().T # Shape: (num_sections, num_candidates)

                # Get top K candidates per section
                top_candidate_ids = torch.topk(similarities, k=min(k, similarities.shape[1]), dim=1).indices # Ensure k is not > num_candidates

                # Predict phenotype based on nearest neighbors
                for s_dx, section in enumerate(non_empty_sections): # Iterate through sections as ordered in weights
                    # Find the corresponding section name in section_to_phenotypes keys if necessary
                    # Assuming the order matches or section_to_phenotypes uses the same section names
                    if section not in section_to_phenotypes:
                         logger.warning(f"Section '{section}' from MIL_weights not found in section_to_phenotypes mapping.")
                         continue

                    for pheno in section_to_phenotypes[section]:
                        neighbor_labels = []
                        for c_id_tensor in top_candidate_ids[s_dx]:
                             c_id = c_id_tensor.item() # Convert tensor index to int
                             if c_id >= len(candidate_studies): continue # Safety check
                             candidate_study_name = candidate_studies[c_id]
                             # Check if phenotype exists and study exists for that phenotype
                             if pheno in candidate_labels and candidate_study_name in candidate_labels[pheno]:
                                  label_value = candidate_labels[pheno][candidate_study_name]
                                  # Ensure label is numeric before adding
                                  if isinstance(label_value, (int, float)):
                                       neighbor_labels.append(label_value)
                                  else:
                                       logger.warning(f"Non-numeric label found for study {candidate_study_name}, phenotype {pheno}: {label_value}")

                        if neighbor_labels:
                             preds[pheno] = float(np.nanmean(neighbor_labels)) # Ensure float for JSON
                        else:
                             preds[pheno] = None # Use None for missing predictions

                logger.info("Metrics prediction complete.")
            except Exception as e:
                 logger.exception("Error during metrics prediction")
                 preds = {"error": "Failed to predict metrics."} # Provide fallback

            # --- 5. Construct Final Result ---
            processing_time = (time.time() - start_time) * 1000
            logger.info(f"Prediction completed in {processing_time:.2f} ms")

            patient_info = {}
            try:
                if hasattr(dicom_dataset, 'PatientName'): patient_info['name'] = str(dicom_dataset.PatientName)
                if hasattr(dicom_dataset, 'PatientID'): patient_info['id'] = dicom_dataset.PatientID
                if hasattr(dicom_dataset, 'StudyDate'): patient_info['study_date'] = dicom_dataset.StudyDate
            except Exception as e:
                logger.warning(f"Error extracting DICOM metadata: {str(e)}")

            result = {
                "model_version": MODEL_VERSION,
                "report": generated_report,
                "metrics": preds,
                # "views": view_list, # Maybe add view list back if needed
                "patient_info": patient_info,
                "processing_time_ms": processing_time
            }
            # Add confidence if applicable/calculated

            return result

        except Exception as e:
            logger.exception(f"Prediction error: {str(e)}")
            raise errors.InternalServerError(f"Prediction failed: {str(e)}")

    # --- default_output_fn (Keep previous version) ---
    def default_output_fn(self,
                         prediction: Dict[str, Any],
                         accept: str) -> Tuple[Union[str, bytes], str]:
        """Serializes the prediction result."""
        logger.info(f"Serializing output with accept type: {accept}")
        accept = content_types.JSON if accept == "*/*" or not accept else accept
        if accept == content_types.JSON:
            try:
                # Convert numpy types to native Python types for JSON serialization
                serializable_prediction = json.loads(json.dumps(prediction, cls=NumpyEncoder))
                result = json.dumps(serializable_prediction, indent=2)
                return result.encode('utf-8'), content_types.JSON
            except Exception as e:
                 logger.exception(f"Error serializing JSON output: {e}")
                 raise errors.InternalServerError(f"Failed to serialize JSON output: {e}")
        else:
            raise errors.UnsupportedFormatError(f"Unsupported accept type: {accept}. Only JSON is supported.")

# Helper class to handle numpy types in JSON serialization
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        elif pd.isna(obj): # Handle pandas NaT or numpy NaN
             return None
        return super(NumpyEncoder, self).default(obj)


# Script entrypoint
if __name__ == "__main__":
    model_server.start_model_server(handler_service=EchoPrimeHandler())
