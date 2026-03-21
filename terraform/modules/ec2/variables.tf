variable "ami" {}
variable "instance_type" {}
variable "key_name" {}
variable "availability_zone" {}
variable "iam_instance_profile" {}
variable "user_data" {}
variable "root_volume_size" {}
variable "root_volume_type" {}
variable "delete_on_termination" {}
variable "security_group_ids" {
  type = list(string)
}
variable "subnet_id" {}
variable "associate_public_ip_address" {
  type    = bool
  default = true
}
variable "tags" {
  type = map(string)
}
