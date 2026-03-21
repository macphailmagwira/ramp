output "user_pool_id" {
  value       = aws_cognito_user_pool.this.id
  description = "Cognito User Pool ID"
}

output "user_pool_arn" {
  value       = aws_cognito_user_pool.this.arn
  description = "Cognito User Pool ARN"
}

output "user_pool_client_id" {
  value       = aws_cognito_user_pool_client.app_client.id
  description = "Cognito User Pool Client ID"
}

output "user_pool_endpoint" {
  value       = aws_cognito_user_pool.this.endpoint
  description = "Cognito User Pool endpoint"
}

output "user_pool_groups" {
  value = {
    for name, group in aws_cognito_user_group.groups : name => {
      name        = group.name
      description = group.description
      precedence  = group.precedence
    }
  }
  description = "Created Cognito User Pool Groups"
}