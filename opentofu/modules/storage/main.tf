resource "aws_kms_key" "s3_key" {
  description             = "${var.name_prefix} S3 bucket encryption key"
  deletion_window_in_days = 10
  enable_key_rotation     = true
  
  tags = merge(var.tags, {
    Name = "${var.name_prefix}-s3-kms-key"
  })
}

resource "aws_kms_alias" "s3_key_alias" {
  name          = "alias/${var.name_prefix}-s3-key"
  target_key_id = aws_kms_key.s3_key.key_id
}

resource "aws_s3_bucket" "sagemaker_bucket" {
  bucket = "${var.name_prefix}-sagemaker-${var.bucket_suffix}"

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-sagemaker"
  })
}

resource "aws_s3_bucket_public_access_block" "sagemaker_bucket_access" {
  bucket = aws_s3_bucket.sagemaker_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "sagemaker_bucket_versioning" {
  bucket = aws_s3_bucket.sagemaker_bucket.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "sagemaker_bucket_encryption" {
  bucket = aws_s3_bucket.sagemaker_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.s3_key.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "sagemaker_bucket_lifecycle" {
  bucket = aws_s3_bucket.sagemaker_bucket.id

  rule {
    id     = "async-inference-results-expiration"
    status = "Enabled"

    expiration {
      days = 30
    }

    filter {
      prefix = "outputs/"
    }
  }
  
  rule {
    id     = "delete-old-versions"
    status = "Enabled"
    
    filter {
      prefix = ""
    }
    
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

resource "aws_s3_bucket_policy" "sagemaker_bucket_policy" {
  bucket = aws_s3_bucket.sagemaker_bucket.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyIncorrectEncryptionHeader"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.sagemaker_bucket.arn}/*"
        Condition = {
          StringNotEquals = {
            "s3:x-amz-server-side-encryption" = "aws:kms"
          }
        }
      },
      {
        Sid       = "DenyUnencryptedObjectUploads"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.sagemaker_bucket.arn}/*"
        Condition = {
          Null = {
            "s3:x-amz-server-side-encryption" = "true"
          }
        }
      },
      {
        Sid       = "EnforceTLSRequestsOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [
          aws_s3_bucket.sagemaker_bucket.arn,
          "${aws_s3_bucket.sagemaker_bucket.arn}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}
