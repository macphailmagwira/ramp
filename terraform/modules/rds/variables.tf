variable "db_identifier" {}
variable "allocated_storage" {}
variable "instance_class" {}
variable "engine" {}
variable "backup_window" {}
variable "backup_retention_period" {}
variable "maintenance_window" {}
variable "multi_az" {}
variable "engine_version" {}
variable "auto_minor_version_upgrade" {}
variable "license_model" {}
variable "publicly_accessible" {}
variable "storage_type" {}
variable "port" {}
variable "storage_encrypted" {}
variable "kms_key_id" {}
variable "copy_tags_to_snapshot" {}
variable "monitoring_interval" {}
variable "iam_database_authentication_enabled" {}
variable "deletion_protection" {}
variable "subnet_group_name" {}
variable "subnet_ids" {
  type = list(string)
}
variable "vpc_security_group_ids" {
  type = list(string)
}

variable "skip_final_snapshot" {
  type    = bool
  default = false
}

variable "username" {
  type        = string
  description = "Master username for RDS"
}

variable "password" {
  type        = string
  description = "Master password for RDS"
  sensitive   = true
}

variable "db_name" {
  type    = string
  default = null
}


variable "final_snapshot_identifier" {
  type    = string
  default = null
}
