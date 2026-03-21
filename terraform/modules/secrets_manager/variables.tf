variable "secrets" {
  type = map(object({
    name : string
  }))
  description = "Map of secret names to read from Secrets Manager"
}
