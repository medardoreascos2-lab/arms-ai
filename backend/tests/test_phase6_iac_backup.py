"""R71G static checks for off-host staging backup provisioning."""

from pathlib import Path


ROOT = Path(__file__).parents[2]
BACKUP = ROOT / "infra" / "phase6" / "aws" / "modules" / "backup"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(BACKUP.glob("*.tf")))


def test_backup_storage_is_private_encrypted_versioned_and_tls_only():
    text = _text()

    for setting in (
        "block_public_acls       = true",
        "block_public_policy     = true",
        "ignore_public_acls      = true",
        "restrict_public_buckets = true",
        'status = "Enabled"',
        'sse_algorithm     = "aws:kms"',
        'sid    = "DenyInsecureTransport"',
        'variable = "aws:SecureTransport"',
        'values   = ["false"]',
    ):
        assert setting in text


def test_retention_and_object_lock_are_explicit_and_bounded():
    text = _text()

    assert "object_lock_enabled = var.object_lock_enabled" in text
    assert 'mode = "GOVERNANCE"' in text
    assert "days = var.retention_days" in text
    assert "var.retention_days >= 7 && var.retention_days <= 365" in text
    assert "noncurrent_days = var.retention_days" in text
    assert "days_after_initiation = 7" in text


def test_backup_writer_and_restore_reader_have_separate_non_destructive_access():
    text = _text()

    assert 'resource "aws_iam_policy" "backup_writer"' in text
    assert 'resource "aws_iam_policy" "restore_reader"' in text
    assert '"s3:PutObject", "s3:AbortMultipartUpload"' in text
    assert '"s3:GetObject", "s3:GetObjectVersion"' in text
    assert "s3:DeleteObject" not in text
    assert "s3:DeleteBucket" not in text
    assert "isolated restore validation" in text


def test_backup_policy_is_prefix_and_key_scoped():
    text = _text()

    assert text.count('"${aws_s3_bucket.backup.arn}/backups/*"') == 2
    assert text.count("Resource = aws_kms_key.backup.arn") == 2
    assert 'StringLike = { "s3:prefix" = ["backups/*"] }' in text
    assert 'Resource = "*"' not in text
