variable "vpc_name" {
  type = string
}

variable "cidr_block" {
  type = string
}

variable "enable_dns_hostnames" {
  type    = bool
  default = true
}

variable "public_subnets" {
  type = list(object({
    az   = string
    cidr = string
  }))
}

variable "private_subnets" {
  type = list(object({
    az   = string
    cidr = string
  }))
  default = []
}

variable "tags" {
  type    = map(string)
  default = {}
}

# NAT Gateway variables
variable "enable_nat_gateway" {
  description = "Should be true if you want to provision NAT Gateways for private subnets"
  type        = bool
  default     = false
}

variable "single_nat_gateway" {
  description = "Should be true if you want to provision a single shared NAT Gateway across all private networks"
  type        = bool
  default     = false
}