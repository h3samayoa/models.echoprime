variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
}

variable "sagemaker_kms_key_arn" {
  description = "ARN of the KMS key used for S3 bucket encryption"
  type        = string
}
