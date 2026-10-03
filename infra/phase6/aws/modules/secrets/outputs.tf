output "secret_arns" {
  description = "Opaque secret references only. Values are absent from Terraform."
  value       = { for name, secret in aws_secretsmanager_secret.reference : name => secret.arn }
}

output "reader_policy_arns" {
  value = { for name, policy in aws_iam_policy.reader : name => policy.arn }
}

output "rotation_contract" {
  value = {
    hook_configured            = var.rotation_lambda_arn != null
    automatically_after_days  = var.rotation_days
    secret_values_in_terraform = false
    environment                = var.environment
  }
}
