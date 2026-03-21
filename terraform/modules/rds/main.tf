

resource "aws_db_subnet_group" "this" {
  name        = var.subnet_group_name
  description = "StitchSense DB subnet group"
  subnet_ids  = var.subnet_ids
}

resource "aws_db_instance" "this" {
  db_name                                = var.db_name
  identifier                          = var.db_identifier
  allocated_storage                   = var.allocated_storage
  instance_class                      = var.instance_class
  engine                              = var.engine
  username                            = var.username
  password                            = var.password
  backup_window                       = var.backup_window
  backup_retention_period             = var.backup_retention_period
  maintenance_window                  = var.maintenance_window
  multi_az                            = var.multi_az
  engine_version                      = var.engine_version
  auto_minor_version_upgrade          = var.auto_minor_version_upgrade
  license_model                       = var.license_model
  publicly_accessible                 = var.publicly_accessible
  storage_type                        = var.storage_type
  port                                = var.port
  storage_encrypted                   = var.storage_encrypted
  kms_key_id                          = var.kms_key_id
  copy_tags_to_snapshot               = var.copy_tags_to_snapshot
  monitoring_interval                 = var.monitoring_interval
  iam_database_authentication_enabled = var.iam_database_authentication_enabled
  deletion_protection                 = var.deletion_protection
  db_subnet_group_name                = aws_db_subnet_group.this.name
  vpc_security_group_ids              = var.vpc_security_group_ids
  skip_final_snapshot                 = var.skip_final_snapshot
  final_snapshot_identifier           = var.skip_final_snapshot ? null : var.final_snapshot_identifier

  lifecycle {
    ignore_changes = [final_snapshot_identifier]
  }
}