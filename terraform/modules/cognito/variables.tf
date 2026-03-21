variable "user_pool_name" {
  type        = string
  description = "Name of the Cognito User Pool"
}

variable "app_client_name" {
  type        = string
  description = "Name of the Cognito user pool client (app)"
}

variable "tags" {
  type        = map(string)
  description = "Tags to apply to the Cognito user pool"
  default     = {}
}

variable "user_pool_groups" {
  description = "List of user pool groups to create"
  type = list(object({
    name        = string
    description = string
    precedence  = number
  }))
  default = []
}

variable "generate_secret" {
  type        = bool
  description = "Whether to generate a client secret for this app client"
  default     = false
}

variable "app_url" {
  type        = string
  description = "The URL of the app to include in invite emails"
}
