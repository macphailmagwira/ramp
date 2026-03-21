variable "table_name" {
  type = string
}

variable "billing_mode" {
  type    = string
  default = "PAY_PER_REQUEST"
}

variable "hash_key" {
  type    = string
  default = "LockID"
}

variable "attributes" {
  type = list(object({
    name = string
    type = string
  }))
}
