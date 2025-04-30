#!/bin/bash
set -e


MODEL_PATH=${MODEL_PATH:-/opt/ml/model}
INFERENCE_PATH=${INFERENCE_PATH:-/opt/program}
PORT=${SAGEMAKER_BIND_TO_PORT:-8080}
GPU_ENABLED=${DISABLE_GPU_CHECK:-false}

mkdir -p "$MODEL_PATH"

if [ "$1" = "prod" ]; then
  echo "Starting EchoPrime in production mode..."
  exec python inference.py
else
  echo "Starting EchoPrime in development mode..."
  exec tail -f /dev/null
fi
