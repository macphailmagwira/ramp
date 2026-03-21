
resource "aws_sqs_queue" "this" {
  for_each = toset(var.queues)
  name     = each.value
}
 