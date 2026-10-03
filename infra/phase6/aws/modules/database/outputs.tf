output "endpoint" {
  description = "Private PostgreSQL endpoint; not a credential."
  value       = aws_db_instance.database.address
}

output "port" {
  value = aws_db_instance.database.port
}

output "resource_id" {
  description = "Stable identifier for scoped IAM database authentication."
  value       = aws_db_instance.database.resource_id
}

output "master_secret_arn" {
  description = "RDS-managed secret reference only; no secret value is exposed."
  value       = aws_db_instance.database.master_user_secret[0].secret_arn
  sensitive   = true
}

output "contract" {
  value = {
    engine                  = "postgresql"
    timezone                = "UTC"
    exact_decimal_semantics = "NUMERIC"
    publicly_accessible     = false
    encrypted               = true
    backup_retention_days   = var.backup_retention_days
    multi_az                = var.multi_az
    max_connections         = var.max_connections
  }
}
