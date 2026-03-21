variable "env" {
  description = "Environment name (staging/prod)"
  type        = string
}

variable "additional_policy_arns" {
  type    = list(string)
  default = []
}


