locals {
  name_prefix = "${var.project_name}-${var.environment}"
  
  common_tags = {
    Environment = var.environment
    Terraform   = "true"
    Project     = var.project_name
    Application = "sagemaker-async-inference"
    Managed_by  = "opentofu"
  }
  
  s3_bucket_name = "${local.name_prefix}-sagemaker-${random_string.bucket_suffix.result}"
  
  ecr_repository_name = split("/", module.ecr.repository_url)[1]
}
