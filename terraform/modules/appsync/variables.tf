
variable "api_name" {
  description = "Name of the AppSync API"
  type        = string
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID for authentication"
  type        = string
}

variable "xray_enabled" {
  description = "Enable X-Ray tracing"
  type        = bool
  default     = false
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}


########################################
# HTTP DataSource Configuration
########################################

variable "enable_http_datasource" {
  description = "Enable HTTP datasource for FastAPI"
  type        = bool
  default     = false
}

variable "fastapi_endpoint" {
  description = "FastAPI endpoint URL (ALB DNS)"
  type        = string
  default     = ""
}

variable "appsync_service_role_arn" {
  description = "IAM role ARN for AppSync to invoke HTTP datasource"
  type        = string
  default     = ""

}


variable "enable_logging" {
  description = "Enable CloudWatch logging for AppSync"
  type        = bool
  default     = false
}

variable "field_log_level" {
  description = "Field logging level (NONE, ERROR, ALL)"
  type        = string
  default     = "NONE"
  validation {
    condition     = contains(["NONE", "ERROR", "ALL"], var.field_log_level)
    error_message = "field_log_level must be NONE, ERROR, or ALL"
  }
}

variable "cloudwatch_logs_role_arn" {
  description = "IAM role ARN for CloudWatch logging"
  type        = string
  default     = null
}

variable "exclude_verbose_content" {
  description = "Exclude verbose content from logs"
  type        = bool
  default     = false
}