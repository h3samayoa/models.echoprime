resource "aws_kms_key" "ecr_key" {
  description             = "${var.name_prefix} ECR repository encryption key"
  deletion_window_in_days = 10
  enable_key_rotation     = true
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-ecr-kms-key"
  })
}

resource "aws_kms_alias" "ecr_key_alias" {
  name          = "alias/${var.name_prefix}-ecr-key"
  target_key_id = aws_kms_key.ecr_key.key_id
}

resource "aws_ecr_repository" "echoprime_repo" {
  name                 = var.name_prefix
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
    kms_key         = aws_kms_key.ecr_key.arn
  }

  lifecycle {
    prevent_destroy = false
  }

  tags = merge(var.tags, {
    Name = var.name_prefix
  })
}

resource "aws_ecr_repository_policy" "echoprime_repo_policy" {
  repository = aws_ecr_repository.echoprime_repo.name

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid    = "AllowPullFromSageMaker",
        Effect = "Allow",
        Principal = {
          Service = "sagemaker.amazonaws.com"
        },
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability"
        ]
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "echoprime_repo_lifecycle" {
  repository = aws_ecr_repository.echoprime_repo.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1,
        description  = "Keep only the last 10 untagged images",
        selection = {
          tagStatus   = "untagged",
          countType   = "imageCountMoreThan",
          countNumber = 10
        },
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2,
        description  = "Keep only the last 30 tagged images",
        selection = {
          tagStatus     = "tagged",
          tagPrefixList = ["v", "build", "commit"],
          countType     = "imageCountMoreThan",
          countNumber   = 30
        },
        action = {
          type = "expire"
        }
      }
    ]
  })
}
