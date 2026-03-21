
variable "image_tag" {
  type        = string
  description = "ECR image tag for staging containers."
  default     = "latest-staging"
}

variable "aws_region" {
  description = "AWS region for StitchSense infra"
  type        = string
  default     = "ap-southeast-1"
}


variable "enable_http_datasource" {
  description = "Enable HTTP datasource for AppSync"
  type        = bool
  default     = true
}