output "root_volume_id" {
  description = "ID of the root EBS volume"
  value       = aws_ebs_volume.root.id
}

output "secondary_volume_id" {
  description = "ID of the secondary EBS volume"
  value       = aws_ebs_volume.secondary.id
}
