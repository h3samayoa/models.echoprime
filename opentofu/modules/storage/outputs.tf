output "bucket_name" {
  description = "Name of the SageMaker S3 bucket"
  value       = aws_s3_bucket.sagemaker_bucket.id
}

output "bucket_arn" {
  description = "ARN of the SageMaker S3 bucket"
  value       = aws_s3_bucket.sagemaker_bucket.arn
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for S3 bucket encryption"
  value       = aws_kms_key.s3_key.arn
}

output "kms_key_id" {
  description = "ID of the KMS key used for S3 bucket encryption"
  value       = aws_kms_key.s3_key.key_id
}
