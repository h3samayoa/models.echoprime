variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
  default     = "us-east-2"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "echoprime"
}

variable "environment" {
  description = "Environment name for resource naming"
  type        = string
  default     = "default"
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Terraform   = "true"
    Project     = "echoprime"
    Application = "sagemaker-async-inference"
    Managed_by  = "opentofu"
  }
}

variable "image_tag" {
  description = "The specific tag (e.g., Git SHA) of the ECR image to deploy"
  type        = string
}
