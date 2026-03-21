variable "repositories" {
  description = "List of ECR repository names to create"
  type        = list(string)
}

variable "lifecycle_policies" {
  description = "Map of repository name to lifecycle policy JSON string"
  type        = map(string)
  default     = {}
}

variable "repository_policies" {
  description = "Map of repository name to repository policy JSON string"
  type        = map(string)
  default     = {}
}

variable "region" {
  type        = string
  description = "AWS region for the ECR registry"
}
