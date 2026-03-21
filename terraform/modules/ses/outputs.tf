########################################
# SES MODULE - modules/ses/outputs.tf
########################################

output "domain_identity_arn" {
  description = "ARN of the SES domain identity"
  value       = aws_ses_domain_identity.main.arn
}

output "domain_identity_verification_token" {
  description = "Verification token for the domain"
  value       = aws_ses_domain_identity.main.verification_token
}

output "dkim_tokens" {
  description = "DKIM tokens for email authentication"
  value       = aws_ses_domain_dkim.main.dkim_tokens
  sensitive   = true
}

output "configuration_set_name" {
  description = "Name of the SES configuration set"
  value       = aws_ses_configuration_set.main.name
}

output "configuration_set_arn" {
  description = "ARN of the SES configuration set"
  value       = aws_ses_configuration_set.main.arn
}

output "verified_email_identities" {
  description = "Map of verified email identities"
  value       = { for k, v in aws_ses_email_identity.emails : k => v.arn }
}

output "template_names" {
  description = "List of created template names"
  value       = [for k, v in aws_ses_template.templates : v.name]
}

output "domain" {
  description = "Domain configured for SES"
  value       = var.domain
}
