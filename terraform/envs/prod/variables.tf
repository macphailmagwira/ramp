variable "image_tag" {
  type        = string
  description = "ECR image tag for production containers."
  default     = "latest"
}


variable "aws_region" {
  description = "AWS region for StitchSense infra"
  type        = string
  default     = "ap-southeast-1"
}
