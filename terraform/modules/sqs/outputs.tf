
output "sqs_queue_arns" {
  value = [for q in aws_sqs_queue.this : q.arn]
}
