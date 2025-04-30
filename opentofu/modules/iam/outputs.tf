# Outputs for IAM module

output "sagemaker_role_arn" {
  description = "ARN of the SageMaker execution role"
  value       = aws_iam_role.sagemaker_role.arn
}
