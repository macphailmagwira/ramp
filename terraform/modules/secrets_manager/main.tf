data "aws_secretsmanager_secret" "secrets" {
  for_each = var.secrets
  name     = each.value.name
}

data "aws_secretsmanager_secret_version" "secrets_version" {
  for_each  = data.aws_secretsmanager_secret.secrets
  secret_id = each.value.id
}
