locals {
  secrets = {
    application_database = {
      purpose = "Application PostgreSQL credential supplied by an approved operator"
      readers = ["api", "worker", "scheduler"]
    }
    research_database = {
      purpose = "Research-only PostgreSQL credential supplied by an approved operator"
      readers = ["research"]
    }
    oidc_client = {
      purpose = "OIDC client material supplied by an approved operator"
      readers = ["api"]
    }
    alert_delivery = {
      purpose = "Sanitized alert destination material supplied by an approved operator"
      readers = ["worker"]
    }
  }

  reader_names = toset(flatten([for secret in local.secrets : secret.readers]))
}

resource "aws_kms_key" "secrets" {
  description             = "ARMS AI staging secret encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-secrets" })
}

resource "aws_kms_alias" "secrets" {
  name          = "alias/${var.name_prefix}-secrets"
  target_key_id = aws_kms_key.secrets.key_id
}

resource "aws_secretsmanager_secret" "reference" {
  for_each = local.secrets

  name                    = "${var.name_prefix}/${var.environment}/${each.key}"
  description             = each.value.purpose
  kms_key_id              = aws_kms_key.secrets.arn
  recovery_window_in_days = 30

  tags = merge(var.tags, {
    Name        = "${var.name_prefix}-${replace(each.key, "_", "-" )}"
    Environment = var.environment
    SecretState = "value-not-managed-by-terraform"
  })
}

resource "aws_secretsmanager_secret_rotation" "approved_hook" {
  for_each = var.rotation_lambda_arn == null ? {} : aws_secretsmanager_secret.reference

  secret_id           = each.value.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = var.rotation_days
  }
}

resource "aws_iam_policy" "reader" {
  for_each = local.reader_names

  name        = "${var.name_prefix}-${each.key}-secrets-read"
  description = "Exact staging secret references for ${each.key}; no list or write authority"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadExactSecrets"
        Effect = "Allow"
        Action = [
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetSecretValue",
        ]
        Resource = [
          for name, secret in local.secrets :
          aws_secretsmanager_secret.reference[name].arn
          if contains(secret.readers, each.key)
        ]
      },
      {
        Sid      = "DecryptExactSecretKey"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [aws_kms_key.secrets.arn]
        Condition = {
          StringEquals = {
            "kms:ViaService" = "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      },
    ]
  })

  tags = var.tags
}

data "aws_region" "current" {}
