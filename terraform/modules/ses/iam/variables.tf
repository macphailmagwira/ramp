########################################
# SES IAM SUBMODULE - modules/ses/iam/variables.tf
########################################

variable "name_prefix" {
  description = "Prefix for IAM policy name"
  type        = string
}

variable "ses_identity_arns" {
  description = "List of SES identity ARNs to allow sending from"
  type        = list(string)
}

variable "iam_role_names" {
  description = "List of IAM role names to attach the SES policy to"
  type        = list(string)
  default     = []
}

variable "restrict_from_addresses" {
  description = "Whether to restrict sending to specific from addresses"
  type        = bool
  default     = false
}

variable "allowed_from_addresses" {
  description = "List of allowed from email addresses (if restrict_from_addresses is true)"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags to apply to IAM resources"
  type        = map(string)
  default     = {}
}
