variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "bucket_suffix" {
  description = "Suffix for S3 bucket name to ensure uniqueness"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
}
