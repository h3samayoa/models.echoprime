output "repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.echoprime_repo.repository_url
}

output "repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.echoprime_repo.arn
}

output "repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.echoprime_repo.name
}

output "kms_key_arn" {
  description = "ARN of the KMS key used for ECR repository encryption"
  value       = aws_kms_key.ecr_key.arn
}
