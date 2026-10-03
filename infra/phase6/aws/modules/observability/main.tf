locals {
  services = toset([
    "api",
    "worker",
    "scheduler",
    "research",
    "migration",
    "backup",
    "restore",
  ])

  sensitive_field_denylist = toset([
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "database_url",
    "account_number",
  ])

  alarm_definitions = {
    rejected_side_effect = {
      metric_name        = "RejectedSideEffectAttempt"
      threshold          = 1
      comparison_operator = "GreaterThanOrEqualToThreshold"
      treat_missing_data = "notBreaching"
    }
    dependency_unavailable = {
      metric_name        = "RequiredDependencyUnavailable"
      threshold          = 1
      comparison_operator = "GreaterThanOrEqualToThreshold"
      treat_missing_data = "notBreaching"
    }
    stale_market_data = {
      metric_name        = "StaleMarketDataBlocked"
      threshold          = 1
      comparison_operator = "GreaterThanOrEqualToThreshold"
      treat_missing_data = "notBreaching"
    }
    telemetry_heartbeat_missing = {
      metric_name        = "TelemetryHeartbeat"
      threshold          = 1
      comparison_operator = "LessThanThreshold"
      treat_missing_data = "breaching"
    }
  }
}

resource "aws_kms_key" "logs" {
  description             = "ARMS AI staging telemetry encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-telemetry" })
}

resource "aws_kms_alias" "logs" {
  name          = "alias/${var.name_prefix}-telemetry"
  target_key_id = aws_kms_key.logs.key_id
}

resource "aws_cloudwatch_log_group" "service" {
  for_each = local.services

  name              = "/arms-ai/staging/${each.key}"
  retention_in_days = var.log_retention_days
  kms_key_id        = aws_kms_key.logs.arn
  skip_destroy      = false
  tags              = merge(var.tags, { Service = each.key })
}

resource "aws_cloudwatch_log_data_protection_policy" "service" {
  for_each = aws_cloudwatch_log_group.service

  log_group_name = each.value.name
  policy_document = jsonencode({
    Name        = "${var.name_prefix}-${each.key}-redaction"
    Description = "Audit and mask common credential and personal-data classes"
    Version     = "2021-06-01"
    Statement = [
      {
        Sid            = "AuditSensitiveData"
        DataIdentifier = [
          "arn:aws:dataprotection::aws:data-identifier/EmailAddress",
          "arn:aws:dataprotection::aws:data-identifier/IpAddress",
          "arn:aws:dataprotection::aws:data-identifier/AwsSecretKey",
        ]
        Operation = {
          Audit = {
            FindingsDestination = {}
          }
        }
      },
      {
        Sid            = "MaskSensitiveData"
        DataIdentifier = [
          "arn:aws:dataprotection::aws:data-identifier/EmailAddress",
          "arn:aws:dataprotection::aws:data-identifier/IpAddress",
          "arn:aws:dataprotection::aws:data-identifier/AwsSecretKey",
        ]
        Operation = {
          Deidentify = {
            MaskConfig = {}
          }
        }
      },
    ]
  })
}

resource "aws_cloudwatch_log_metric_filter" "safety_event" {
  for_each = {
    rejected_side_effect = "{ $.event = \"REJECTED_SIDE_EFFECT_ATTEMPT\" }"
    dependency_unavailable = "{ $.event = \"REQUIRED_DEPENDENCY_UNAVAILABLE\" }"
    stale_market_data = "{ $.event = \"STALE_MARKET_DATA_BLOCKED\" }"
  }

  name           = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  pattern        = each.value
  log_group_name = aws_cloudwatch_log_group.service["api"].name

  metric_transformation {
    name      = local.alarm_definitions[each.key].metric_name
    namespace = "ARMSAI/Staging/Safety"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_sns_topic" "alerts" {
  name              = "${var.name_prefix}-alerts"
  kms_master_key_id = "alias/aws/sns"
  tags              = var.tags
}

resource "aws_cloudwatch_metric_alarm" "safety" {
  for_each = local.alarm_definitions

  alarm_name          = "${var.name_prefix}-${replace(each.key, "_", "-")}"
  alarm_description   = "ARMS AI staging ${each.key}; payloads contain no secret values"
  namespace           = "ARMSAI/Staging/Safety"
  metric_name         = each.value.metric_name
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = var.alarm_evaluation_periods
  threshold           = each.value.threshold
  comparison_operator = each.value.comparison_operator
  treat_missing_data  = each.value.treat_missing_data
  alarm_actions       = [aws_sns_topic.alerts.arn]
  ok_actions          = [aws_sns_topic.alerts.arn]
  tags                = var.tags
}

resource "aws_cloudwatch_dashboard" "staging" {
  dashboard_name = "${var.name_prefix}-operations"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "Safety blocks and dependency availability"
          region = data.aws_region.current.name
          view   = "timeSeries"
          metrics = [
            for alarm in values(local.alarm_definitions) :
            ["ARMSAI/Staging/Safety", alarm.metric_name]
          ]
        }
      },
      {
        type   = "text"
        width  = 12
        height = 4
        properties = {
          markdown = "# ARMS AI staging\nSynthetic/NQ/MNQ-scoped evidence only. No broker, PAPER, LIVE, or production authority."
        }
      },
    ]
  })
}

resource "aws_iam_policy" "telemetry_writer" {
  name        = "${var.name_prefix}-telemetry-write"
  description = "Write-only access to exact staging log groups and metric namespace"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteServiceLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = [for group in aws_cloudwatch_log_group.service : "${group.arn}:*"]
      },
      {
        Sid      = "WriteBoundedMetrics"
        Effect   = "Allow"
        Action   = ["cloudwatch:PutMetricData"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "ARMSAI/Staging/Safety"
          }
        }
      },
    ]
  })

  tags = var.tags
}

data "aws_region" "current" {}
