output "role_name" {
  description = "Name of the IAM role"
  value       = aws_iam_role.ec2_role.name
}

output "profile" {
  description = "IAM instance profile name to attach to EC2"
  value       = aws_iam_instance_profile.ec2_profile.name
}
output "appsync_service_role_arn" {
  value = aws_iam_role.appsync_vpc.arn
}
