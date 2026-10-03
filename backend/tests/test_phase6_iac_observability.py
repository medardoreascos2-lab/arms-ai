"""R71F static checks for bounded, redacted staging observability."""

from pathlib import Path


ROOT = Path(__file__).parents[2]
OBSERVABILITY = ROOT / "infra" / "phase6" / "aws" / "modules" / "observability"


def _text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(OBSERVABILITY.glob("*.tf")))


def test_logs_are_encrypted_retained_and_cover_every_workload():
    text = _text()

    for service in ("api", "worker", "scheduler", "research", "migration", "backup", "restore"):
        assert f'"{service}"' in text
    assert "retention_in_days = var.log_retention_days" in text
    assert "kms_key_id        = aws_kms_key.logs.arn" in text
    assert "enable_key_rotation     = true" in text


def test_data_protection_and_application_redaction_contract_are_explicit():
    text = _text()

    assert 'resource "aws_cloudwatch_log_data_protection_policy"' in text
    assert "AwsSecretKey" in text
    assert "MaskConfig" in text
    for field in ("authorization", "cookie", "password", "secret", "token", "database_url", "account_number"):
        assert f'"{field}"' in text


def test_safety_alarms_include_missing_heartbeat_and_no_external_subscription():
    text = _text()

    for metric in (
        "RejectedSideEffectAttempt",
        "RequiredDependencyUnavailable",
        "StaleMarketDataBlocked",
        "TelemetryHeartbeat",
    ):
        assert metric in text
    assert 'treat_missing_data = "breaching"' in text
    assert 'resource "aws_sns_topic_subscription"' not in text
    assert "external_route_configured = false" in text


def test_telemetry_writer_is_bounded_to_exact_logs_and_metric_namespace():
    text = _text()

    assert '"logs:CreateLogStream"' in text
    assert '"logs:PutLogEvents"' in text
    assert '"cloudwatch:PutMetricData"' in text
    assert '"cloudwatch:namespace" = "ARMSAI/Staging/Safety"' in text
    assert "logs:*" not in text
    assert "cloudwatch:*" not in text


def test_dashboard_repeats_zero_authority_boundary():
    text = _text()

    assert "No broker, PAPER, LIVE, or production authority" in text
    assert "broker_authority          = false" in text
    assert "live_authority            = false" in text
