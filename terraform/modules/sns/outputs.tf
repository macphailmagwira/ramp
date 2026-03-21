output "sns_topic_arns" {
  value = [for t in aws_sns_topic.this : t.arn]
}