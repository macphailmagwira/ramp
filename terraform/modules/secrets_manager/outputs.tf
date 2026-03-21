output "secrets" {
  value = { for key, secret in data.aws_secretsmanager_secret_version.secrets_version :
    key => secret.secret_string
  }
  sensitive = true
}