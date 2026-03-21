variable "certificates" {
  description = "Map of ACM certificates to manage"
  type = map(object({
    domain_name               = string
    subject_alternative_names = optional(list(string), [])
    validation_method         = optional(string, "DNS")
  }))
}

variable "route53_zone_id" {
  description = "Hosted Zone ID for DNS validation (optional)"
  type        = string
  default     = ""
}
