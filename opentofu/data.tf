data "aws_ecr_image" "echoprime_image" {
  repository_name = local.ecr_repository_name
  image_tag       = var.image_tag
}
