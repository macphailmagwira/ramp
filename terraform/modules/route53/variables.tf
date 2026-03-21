variable "domain_name" {
  type = string
}

variable "hosted_zone_id" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
