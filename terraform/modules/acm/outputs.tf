output "certificate_arns" {
  description = "ARNs of all managed ACM certificates"
  value       = { for k, v in aws_acm_certificate.cert : k => v.arn }
}
