# Create ECR repositories
resource "aws_ecr_repository" "this" {
  for_each = toset(var.repositories)
  name     = each.value

  image_scanning_configuration {
    scan_on_push = true
  }
}

# Apply lifecycle policies
resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = { for k, v in var.lifecycle_policies : k => v }
  repository = aws_ecr_repository.this[each.key].name
  policy     = each.value
}

# Apply repository policies
resource "aws_ecr_repository_policy" "this" {
  for_each   = { for k, v in var.repository_policies : k => v }
  repository = aws_ecr_repository.this[each.key].name
  policy     = each.value
}
