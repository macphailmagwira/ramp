# Outputs
output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = [for s in aws_subnet.public : s.id]
}

output "private_subnet_ids" {
  value = [for s in aws_subnet.private : s.id]
}

output "internet_gateway_id" {
  value = aws_internet_gateway.this.id
}

output "public_route_table_id" {
  value = aws_route_table.public.id
}

output "nat_gateway_ids" {
  description = "Map of NAT Gateway IDs"
  value       = { for k, v in aws_nat_gateway.this : k => v.id }
}

output "nat_gateway_public_ips" {
  description = "Map of public Elastic IPs created for NAT Gateways"
  value       = { for k, v in aws_eip.nat : k => v.public_ip }
}

output "private_route_table_ids" {
  description = "Map of private route table IDs"
  value       = { for k, v in aws_route_table.private : k => v.id }
}