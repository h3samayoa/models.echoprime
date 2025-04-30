# Main configuration file for EchoPrime infrastructure

# Random string for bucket name uniqueness
resource "random_string" "bucket_suffix" {
  length  = 8
  special = false
  lower   = true
  upper   = false
  numeric = true
}

# IAM module for roles and policies
module "iam" {
  source = "./modules/iam"
  
  name_prefix           = local.name_prefix
  tags                  = local.common_tags
  sagemaker_kms_key_arn = module.storage.kms_key_arn # Pass KMS key ARN from storage module
}

# Storage module for S3 bucket
module "storage" {
  source = "./modules/storage"
  
  name_prefix   = local.name_prefix
  bucket_suffix = random_string.bucket_suffix.result
  tags          = local.common_tags
}

# ECR module for container registry
module "ecr" {
  source = "./modules/ecr"
  
  name_prefix = local.name_prefix
  tags        = local.common_tags
}
