# IAM Resources for EchoPrime SageMaker Deployment

# SageMaker Execution Role
resource "aws_iam_role" "sagemaker_role" {
  name        = "${var.name_prefix}-sagemaker-role"
  description = "IAM role for SageMaker to access AWS resources"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "sagemaker.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-sagemaker-role"
  })
}

resource "aws_iam_policy" "sagemaker_policy" {
  name        = "${var.name_prefix}-sagemaker-policy"
  description = "Policy for SageMaker to access required AWS resources"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ],
        Resource = [
          "arn:aws:s3:::${var.name_prefix}-sagemaker-*",
          "arn:aws:s3:::${var.name_prefix}-sagemaker-*/*"
        ]
      },
      {
        Effect = "Allow",
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ],
        Resource = "arn:aws:ecr:*:*:repository/${var.name_prefix}"
      },
      {
        Effect   = "Allow",
        Action   = "ecr:GetAuthorizationToken",
        Resource = "*"
      },
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:log-group:/aws/sagemaker/*"
      },
      {
        Effect = "Allow",
        Action = [
          "sns:Publish"
        ],
        Resource = "arn:aws:sns:*:*:${var.name_prefix}-sagemaker-*"
      },
      {
        Effect = "Allow",
        Action = "kms:Decrypt",
        Resource = var.sagemaker_kms_key_arn
      }
    ]
  })
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-sagemaker-policy"
  })
}

resource "aws_iam_role_policy_attachment" "sagemaker_policy_attachment" {
  role       = aws_iam_role.sagemaker_role.name
  policy_arn = aws_iam_policy.sagemaker_policy.arn
}
