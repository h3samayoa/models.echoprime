terraform {
  backend "s3" {
    bucket         = "echoprime-ot-state"
    key            = "echoprime/terraform.tfstate"
    region         = "us-east-2"
    encrypt        = true
    dynamodb_table = "echoprime-terraform-locks"
  }
}

resource "aws_dynamodb_table" "terraform_locks" {
  name         = "echoprime-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  
  attribute {
    name = "LockID"
    type = "S"
  }
  
  tags = merge(local.common_tags, {
    Name = "echoprime-terraform-locks"
  })
}
