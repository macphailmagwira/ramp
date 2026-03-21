output "repository_arns" {
  value = { for k, v in aws_ecr_repository.this : k => v.arn }
}

output "repository_urls" {
  value = { for k, v in aws_ecr_repository.this : k => v.repository_url }
}

data "aws_caller_identity" "current" {}

output "registry" {
  value       = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
  description = "ECR registry URL"
}
