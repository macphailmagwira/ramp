resource "aws_vpc" "this" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = var.enable_dns_hostnames
  instance_tenancy     = "default"

  tags = merge(var.tags, { Name = var.vpc_name })
}

resource "aws_subnet" "public" {
  for_each = { for i, s in var.public_subnets : i => s }

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = merge(var.tags, { Name = "${var.vpc_name}-public-${each.key}" })
}

resource "aws_subnet" "private" {
  for_each = { for i, s in var.private_subnets : i => s }

  vpc_id                  = aws_vpc.this.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = false

  tags = merge(var.tags, { Name = "${var.vpc_name}-private-${each.key}" })
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.vpc_name}-igw" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.vpc_name}-public-rt" })
}

# Route for public subnet to Internet Gateway
resource "aws_route" "public_internet_gateway" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.this.id
}

resource "aws_route_table_association" "public" {
  for_each       = aws_subnet.public
  subnet_id      = each.value.id
  route_table_id = aws_route_table.public.id
}

#############################################
# NAT Gateway Resources
#############################################

# Elastic IP for NAT Gateway
resource "aws_eip" "nat" {
  for_each = var.enable_nat_gateway ? (var.single_nat_gateway ? { "0" = var.public_subnets[0] } : { for i, s in var.public_subnets : i => s }) : {}
  
  domain = "vpc"

  tags = merge(
    var.tags,
    {
      Name = "${var.vpc_name}-nat-eip-${each.key}"
    }
  )

  depends_on = [aws_internet_gateway.this]
}

# NAT Gateway
resource "aws_nat_gateway" "this" {
  for_each = var.enable_nat_gateway ? (var.single_nat_gateway ? { "0" = var.public_subnets[0] } : { for i, s in var.public_subnets : i => s }) : {}
  
  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id

  tags = merge(
    var.tags,
    {
      Name = "${var.vpc_name}-nat-gateway-${each.key}"
    }
  )

  depends_on = [aws_internet_gateway.this]
}

# Private Route Tables (one per private subnet for flexibility with NAT)
resource "aws_route_table" "private" {
  for_each = { for i, s in var.private_subnets : i => s }
  
  vpc_id = aws_vpc.this.id
  
  tags = merge(var.tags, { 
    Name = "${var.vpc_name}-private-rt-${each.key}" 
  })
}

# Route to NAT Gateway for private subnets
resource "aws_route" "private_nat_gateway" {
  for_each = var.enable_nat_gateway ? { for i, s in var.private_subnets : i => s } : {}
  
  route_table_id         = aws_route_table.private[each.key].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = var.single_nat_gateway ? aws_nat_gateway.this["0"].id : aws_nat_gateway.this[each.key].id
}

# Private Subnet Route Table Associations
resource "aws_route_table_association" "private" {
  for_each = aws_subnet.private
  
  subnet_id      = each.value.id
  route_table_id = aws_route_table.private[each.key].id
}