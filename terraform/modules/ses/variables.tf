########################################
# SES MODULE - modules/ses/variables.tf
########################################

variable "domain" {
  description = "Domain name to verify for SES"
  type        = string
}

variable "configuration_set_name" {
  description = "Name of the SES configuration set"
  type        = string
}

variable "environment" {
  description = "Environment name (staging, production, etc.)"
  type        = string
  default     = "staging"
}

# Route53 Configuration
variable "create_route53_records" {
  description = "Whether to create Route53 records for domain verification and DKIM"
  type        = bool
  default     = true
}

variable "route53_zone_id" {
  description = "Route53 hosted zone ID for DNS records"
  type        = string
  default     = ""
}

# Configuration Set Options
variable "tls_policy" {
  description = "TLS policy for emails (Optional or Require)"
  type        = string
  default     = "Require"
  
  validation {
    condition     = contains(["Optional", "Require"], var.tls_policy)
    error_message = "TLS policy must be either 'Optional' or 'Require'."
  }
}

variable "enable_reputation_metrics" {
  description = "Enable reputation metrics for the configuration set"
  type        = bool
  default     = true
}

variable "sending_enabled" {
  description = "Enable sending for the configuration set"
  type        = bool
  default     = true
}

# CloudWatch Events
variable "enable_cloudwatch_events" {
  description = "Enable CloudWatch event destination"
  type        = bool
  default     = true
}

variable "cloudwatch_event_types" {
  description = "Types of events to send to CloudWatch"
  type        = list(string)
  default     = ["send", "bounce", "complaint", "delivery", "reject"]
}

# SNS Events
variable "enable_sns_events" {
  description = "Enable SNS event destination for bounces and complaints"
  type        = bool
  default     = false
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for bounce/complaint notifications"
  type        = string
  default     = ""
}

variable "sns_event_types" {
  description = "Types of events to send to SNS"
  type        = list(string)
  default     = ["bounce", "complaint"]
}

# Email Templates
variable "email_templates" {
  description = "Map of email templates to create"
  type = map(object({
    subject = string
    html    = string
    text    = string
  }))
  default = {}
}

# Verified Email Addresses
variable "verified_emails" {
  description = "List of email addresses to verify (for sandbox testing)"
  type        = list(string)
  default     = []
}

# Email Receiving (optional)
variable "enable_email_receiving" {
  description = "Enable SES to receive emails"
  type        = bool
  default     = false
}

variable "receipt_rule_set_name" {
  description = "Name of the receipt rule set"
  type        = string
  default     = "default-rule-set"
}

# Tags
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
