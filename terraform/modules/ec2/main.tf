resource "aws_instance" "this" {
  ami                  = var.ami
  instance_type        = var.instance_type
  key_name             = var.key_name
  availability_zone    = var.availability_zone
  iam_instance_profile = var.iam_instance_profile

  # These should match how the instance was originally created.
  subnet_id = var.subnet_id

  vpc_security_group_ids = var.security_group_ids

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = var.root_volume_type
    delete_on_termination = var.delete_on_termination
  }

  user_data = var.user_data

  tags = var.tags
 
}
