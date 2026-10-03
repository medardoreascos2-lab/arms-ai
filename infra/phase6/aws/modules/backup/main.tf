resource "aws_kms_key" "backup" {
  description             = "ARMS AI staging off-host backup encryption"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = merge(var.tags, { Name = "${var.name_prefix}-backup" })
}

resource "aws_kms_alias" "backup" {
  name          = "alias/${var.name_prefix}-backup"
  target_key_id = aws_kms_key.backup.key_id
}

resource "aws_s3_bucket" "backup" {
  bucket              = var.bucket_name
  object_lock_enabled = var.object_lock_enabled
  tags                = merge(var.tags, { Name = "${var.name_prefix}-backup" })
}

resource "aws_s3_bucket_public_access_block" "backup" {
  bucket = aws_s3_bucket.backup.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "backup" {
  bucket = aws_s3_bucket.backup.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id

  rule {
    bucket_key_enabled = true

    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.backup.arn
    }
  }
}

resource "aws_s3_bucket_object_lock_configuration" "backup" {
  count = var.object_lock_enabled ? 1 : 0

  bucket = aws_s3_bucket.backup.id

  rule {
    default_retention {
      mode = "GOVERNANCE"
      days = var.retention_days
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "backup" {
  bucket = aws_s3_bucket.backup.id

  rule {
    id     = "bounded-backup-retention"
    status = "Enabled"

    filter {
      prefix = "backups/"
    }

    expiration {
      days = var.retention_days
    }

    noncurrent_version_expiration {
      noncurrent_days = var.retention_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  depends_on = [aws_s3_bucket_versioning.backup]
}

data "aws_iam_policy_document" "transport" {
  statement {
    sid    = "DenyInsecureTransport"
    effect = "Deny"

    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.backup.arn,
      "${aws_s3_bucket.backup.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "transport" {
  bucket = aws_s3_bucket.backup.id
  policy = data.aws_iam_policy_document.transport.json
}

resource "aws_iam_policy" "backup_writer" {
  name        = "${var.name_prefix}-backup-write"
  description = "Write-only staging backup objects with exact bucket scope"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListBackupPrefix"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.backup.arn
        Condition = {
          StringLike = { "s3:prefix" = ["backups/*"] }
        }
      },
      {
        Sid      = "WriteBackupObjects"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:AbortMultipartUpload"]
        Resource = "${aws_s3_bucket.backup.arn}/backups/*"
      },
      {
        Sid      = "EncryptBackupObjects"
        Effect   = "Allow"
        Action   = ["kms:Encrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.backup.arn
      },
    ]
  })
  tags = var.tags
}

resource "aws_iam_policy" "restore_reader" {
  name        = "${var.name_prefix}-restore-read"
  description = "Read-only staging backup access for isolated restore validation"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ListBackupPrefix"
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.backup.arn
        Condition = {
          StringLike = { "s3:prefix" = ["backups/*"] }
        }
      },
      {
        Sid      = "ReadBackupObjects"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:GetObjectVersion"]
        Resource = "${aws_s3_bucket.backup.arn}/backups/*"
      },
      {
        Sid      = "DecryptBackupObjects"
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = aws_kms_key.backup.arn
      },
    ]
  })
  tags = var.tags
}
