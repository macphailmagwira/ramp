variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.11"
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Lambda memory size in MB"
  type        = number
  default     = 256
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "target_queue_url" {
  description = "SQS queue URL to send messages to"
  type        = string
}

variable "target_queue_arn" {
  description = "SQS queue ARN to send messages to"
  type        = string
}

variable "environment_variables" {
  description = "Additional environment variables for Lambda"
  type        = map(string)
  default     = {}
}

variable "enable_s3_trigger" {
  description = "Enable S3 trigger for Lambda"
  type        = bool
  default     = true
}

variable "create_s3_notification" {
  description = "Create S3 bucket notification configuration"
  type        = bool
  default     = true
}

variable "s3_bucket_id" {
  description = "S3 bucket ID for notifications"
  type        = string
  default     = ""
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN for Lambda permissions"
  type        = string
  default     = ""
}

variable "s3_events" {
  description = "S3 events to trigger Lambda"
  type        = list(string)
  default     = ["s3:ObjectCreated:*"]
}

variable "s3_filter_prefix" {
  description = "S3 object key prefix filter"
  type        = string
  default     = ""
}

variable "s3_filter_suffix" {
  description = "S3 object key suffix filter"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to resources"
  type        = map(string)
  default     = {}
}