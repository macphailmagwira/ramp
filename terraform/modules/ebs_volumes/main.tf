
variable "availability_zone" {
  type = string
}

resource "aws_ebs_volume" "root" {
  availability_zone = var.availability_zone
  size              = 30
  type              = "gp3"
  snapshot_id       = "snap-03800cc7ea29f2c3f"

  tags = {
    Name = "rds-ebs"
  }
}

resource "aws_ebs_volume" "secondary" {
  availability_zone = var.availability_zone
  size              = 30
  type              = "gp3"
  snapshot_id       = "snap-03aa2c6c269bf4c29"

  tags = {
    Name    = "restore-test"
    Type    = "ebs-restore-test"
    Purpose = "drill"
  }
}
