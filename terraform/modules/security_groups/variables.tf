variable "name" {}
variable "description" {}
variable "vpc_id" {}
variable "ingress" {
  type = list(object({
    from_port       = number
    to_port         = number
    protocol        = string
    cidr_blocks     = optional(list(string), [])
    security_groups = optional(list(string), [])
  }))
}
variable "tags" {
  type = map(string)
}
