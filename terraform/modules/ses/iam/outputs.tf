########################################
# SES IAM SUBMODULE - modules/ses/iam/outputs.tf
########################################

output "policy_arn" {
  description = "ARN of the SES send email policy"
  value       = aws_iam_policy.ses_send_email.arn
}

output "policy_name" {
  description = "Name of the SES send email policy"
  value       = aws_iam_policy.ses_send_email.name
}
