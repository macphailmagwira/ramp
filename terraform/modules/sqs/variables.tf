variable "queues" {
  type        = list(string)
  description = "List of SQS queue names"
  default     = []
}