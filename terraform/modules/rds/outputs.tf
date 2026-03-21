output "db_instance_id" {
  value = aws_db_instance.this.id
}

output "db_instance_endpoint" {
  value = aws_db_instance.this.endpoint
}

output "db_subnet_group" {
  value = aws_db_subnet_group.this.name
}
