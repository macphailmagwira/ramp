
variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnets" {
  type = list(string)
}

variable "cert_arn" {
  type = string
}

variable "environment" {
  type = string
}

variable "target_groups" {
  description = "Map of target groups: { name = { port, protocol, optional health_check_path } }"
  type = map(object({
    port              = number
    protocol          = string
    health_check_path = optional(string)
  }))
}


variable "internal" {
  description = "Whether the ALB is internal or internet-facing"
  type        = bool
  default     = false
}

variable "security_groups" {
  description = "List of SGs for ALB"
  type        = list(string)
  default     = []
}

variable "allow_http" {
  description = "Enable optional HTTP listener"
  type        = bool
  default     = false
}
 