resource "aws_sns_topic" "this" {
  for_each = toset(var.topics)
  name     = each.value
}