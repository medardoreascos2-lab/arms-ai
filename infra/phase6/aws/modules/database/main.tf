resource "aws_kms_key" "database" {
  description             = "ARMS AI staging PostgreSQL encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-database" })
}

resource "aws_kms_alias" "database" {
  name          = "alias/${var.name_prefix}-database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_db_subnet_group" "database" {
  name       = "${var.name_prefix}-database"
  subnet_ids = var.database_subnet_ids
  tags       = merge(var.tags, { Name = "${var.name_prefix}-database" })
}

resource "aws_db_parameter_group" "database" {
  name_prefix = "${var.name_prefix}-postgres${var.engine_major_version}-"
  family      = "postgres${var.engine_major_version}"
  description = "Fail-closed ARMS AI staging PostgreSQL parameters"

  parameter {
    name  = "timezone"
    value = "UTC"
  }

  parameter {
    name  = "log_timezone"
    value = "UTC"
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }

  parameter {
    name         = "max_connections"
    value        = tostring(var.max_connections)
    apply_method = "pending-reboot"
  }

  parameter {
    name  = "idle_in_transaction_session_timeout"
    value = "60000"
  }

  parameter {
    name  = "statement_timeout"
    value = "120000"
  }

  parameter {
    name  = "log_connections"
    value = "1"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = var.tags
}

resource "aws_db_instance" "database" {
  identifier = "${var.name_prefix}-postgres"

  engine         = "postgres"
  engine_version = var.engine_major_version
  instance_class = var.instance_class

  db_name                     = "arms_staging"
  username                    = "arms_admin"
  manage_master_user_password = true
  master_user_secret_kms_key_id = aws_kms_key.database.arn

  allocated_storage     = var.allocated_storage_gib
  max_allocated_storage = var.max_allocated_storage_gib
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.database.arn

  db_subnet_group_name   = aws_db_subnet_group.database.name
  vpc_security_group_ids = [var.database_security_group_id]
  publicly_accessible    = false
  port                   = 5432

  parameter_group_name = aws_db_parameter_group.database.name
  multi_az             = var.multi_az

  backup_retention_period = var.backup_retention_days
  backup_window           = var.backup_window
  maintenance_window      = var.maintenance_window
  copy_tags_to_snapshot   = true
  skip_final_snapshot     = false
  final_snapshot_identifier = "${var.name_prefix}-postgres-final"
  deletion_protection       = true

  auto_minor_version_upgrade      = true
  apply_immediately               = false
  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true
  iam_database_authentication_enabled = true

  tags = merge(var.tags, {
    Name                 = "${var.name_prefix}-postgres"
    NumericSemantics     = "postgresql-numeric-exact"
    SessionTimezone      = "UTC"
    PubliclyAccessible   = "false"
  })
}
