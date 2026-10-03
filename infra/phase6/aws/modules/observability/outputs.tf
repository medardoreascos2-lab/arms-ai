output "log_group_names" {
  value = { for name, group in aws_cloudwatch_log_group.service : name => group.name }
}

output "alert_topic_arn" {
  description = "Topic only; no external subscription or destination is created."
  value       = aws_sns_topic.alerts.arn
}

output "telemetry_writer_policy_arn" {
  value = aws_iam_policy.telemetry_writer.arn
}

output "telemetry_contract" {
  value = {
    namespace                 = "ARMSAI/Staging/Safety"
    log_retention_days        = var.log_retention_days
    redaction_field_denylist  = sort(tolist(local.sensitive_field_denylist))
    external_route_configured = false
    broker_authority          = false
    live_authority            = false
  }
}
