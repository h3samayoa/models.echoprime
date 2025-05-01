output "sagemaker_role_arn" {
  description = "ARN of the SageMaker execution role"
  value       = module.iam.sagemaker_role_arn
}

output "sagemaker_bucket_name" {
  description = "Name of the S3 bucket for SageMaker data"
  value       = module.storage.bucket_name
}

output "sagemaker_bucket_arn" {
  description = "ARN of the S3 bucket for SageMaker data"
  value       = module.storage.bucket_arn
}

output "sagemaker_bucket_kms_key_arn" {
  description = "ARN of the KMS key used for S3 bucket encryption"
  value       = module.storage.kms_key_arn
}

output "sagemaker_endpoint_name" {
  description = "Name of the SageMaker endpoint"
  value       = aws_sagemaker_endpoint.echoprime_endpoint.name
}

output "terraform_state_bucket" {
  description = "Name of the S3 bucket for Terraform state"
  value       = "echoprime-terraform-state"
}

output "terraform_state_lock_table" {
  description = "Name of the DynamoDB table for Terraform state locking"
  value       = aws_dynamodb_table.terraform_locks.name
}

output "github_actions_configuration" {
  description = "Configuration information for GitHub Actions"
  value = {
    region       = var.aws_region
    # ecr_repo_url removed as ECR is managed externally
  }
}
