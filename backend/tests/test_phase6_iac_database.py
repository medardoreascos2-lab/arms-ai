"""R71C static safety checks for managed staging PostgreSQL."""

from pathlib import Path
import re


ROOT = Path(__file__).parents[2]
DATABASE = ROOT / "infra" / "phase6" / "aws" / "modules" / "database"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(DATABASE.glob("*.tf")))


def test_database_is_private_encrypted_and_recoverable():
    text = _text()

    for declaration in (
        "storage_encrypted     = true",
        "publicly_accessible    = false",
        "manage_master_user_password = true",
        "backup_retention_period = var.backup_retention_days",
        "skip_final_snapshot     = false",
        "deletion_protection       = true",
        "enable_key_rotation     = true",
    ):
        assert declaration in text
    assert re.search(r'password\s*=\s*"', text, re.I) is None


def test_database_enforces_utc_tls_connection_bounds_and_exact_decimal_contract():
    text = _text()

    assert 'name  = "timezone"' in text
    assert 'name  = "log_timezone"' in text
    assert text.count('value = "UTC"') == 2
    assert 'name  = "rds.force_ssl"' in text
    assert 'name         = "max_connections"' in text
    assert 'exact_decimal_semantics = "NUMERIC"' in text
    assert 'var.max_connections >= 20 && var.max_connections <= 500' in text


def test_database_maintenance_backup_and_ha_are_explicit():
    text = _text()

    assert 'maintenance_window      = var.maintenance_window' in text
    assert 'backup_window           = var.backup_window' in text
    assert 'var.backup_retention_days >= 7 && var.backup_retention_days <= 35' in text
    assert 'multi_az             = var.multi_az' in text
    assert 'enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]' in text


def test_database_outputs_no_plaintext_secret_value():
    outputs = (DATABASE / "outputs.tf").read_text(encoding="utf-8")

    assert "master_secret_arn" in outputs
    assert "secret_arn" in outputs
    assert "secret_string" not in outputs
    assert "password" not in outputs.lower()
