"""R71D static checks for secret-free Secrets Manager provisioning."""

from pathlib import Path
import re


ROOT = Path(__file__).parents[2]
SECRETS = ROOT / "infra" / "phase6" / "aws" / "modules" / "secrets"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(SECRETS.glob("*.tf")))


def test_secret_metadata_has_environment_isolation_encryption_and_recovery():
    text = _text()

    assert 'condition     = var.environment == "staging"' in text
    assert 'name                    = "${var.name_prefix}/${var.environment}/${each.key}"' in text
    assert 'kms_key_id              = aws_kms_key.secrets.arn' in text
    assert 'enable_key_rotation     = true' in text
    assert 'recovery_window_in_days = 30' in text


def test_terraform_never_defines_secret_values():
    text = _text()

    assert 'resource "aws_secretsmanager_secret_version"' not in text
    assert "secret_string" not in text
    assert "secret_binary" not in text
    assert re.search(r'(password|token|credential)\s*=\s*"', text, re.I) is None
    assert 'secret_values_in_terraform = false' in text


def test_reader_policies_are_exact_read_only_and_have_no_wildcards():
    text = _text()

    assert '"secretsmanager:GetSecretValue"' in text
    assert '"secretsmanager:DescribeSecret"' in text
    assert 'secretsmanager:ListSecrets' not in text
    assert 'secretsmanager:PutSecretValue' not in text
    assert re.search(r'Resource\s*=\s*"\*"', text) is None
    assert 'Action   = ["kms:Decrypt"]' in text
    assert '"kms:ViaService"' in text


def test_service_scopes_keep_application_and_research_database_secrets_separate():
    text = _text()

    assert 'readers = ["api", "worker", "scheduler"]' in text
    assert 'readers = ["research"]' in text
    assert 'readers = ["api"]' in text
    assert 'readers = ["worker"]' in text


def test_rotation_is_optional_and_requires_an_explicit_approved_hook():
    text = _text()

    assert 'default     = null' in text
    assert 'var.rotation_lambda_arn == null ? {}' in text
    assert 'automatically_after_days = var.rotation_days' in text
