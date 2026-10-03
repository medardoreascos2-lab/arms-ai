output "bucket_arn" {
  value = aws_s3_bucket.backup.arn
}

output "backup_writer_policy_arn" {
  value = aws_iam_policy.backup_writer.arn
}

output "restore_reader_policy_arn" {
  value = aws_iam_policy.restore_reader.arn
}

output "backup_contract" {
  value = {
    prefix              = "backups/"
    encrypted           = true
    versioning          = true
    public_access       = false
    retention_days      = var.retention_days
    object_lock_enabled = var.object_lock_enabled
    restore_isolated    = true
  }
}
