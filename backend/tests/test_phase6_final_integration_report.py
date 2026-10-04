"""R77B final integration report contract tests."""

from pathlib import Path


REPORT = Path(__file__).parents[2] / "docs" / "phase6" / "PHASE6_FINAL_INTEGRATION_R77B.md"


def _report() -> str:
    return REPORT.read_text(encoding="utf-8")


def test_report_covers_required_phase6_evidence():
    text = _report()

    for heading in (
        "Architecture and provider decision",
        "Infrastructure as code",
        "NQ and MNQ support",
        "Security and resilience evidence",
        "Final test results",
        "Cost category",
        "External actions still requiring explicit approval",
    ):
        assert heading in text
    assert "AWS is the selected staging provider" in text
    assert "**1498 passed**" in text
    assert "`ESTIMATED_COST_CATEGORY=MEDIUM`" in text


def test_report_preserves_operator_and_trading_authority_boundaries():
    text = _report()

    assert "`PROVISIONING_STATUS=READY_FOR_OPERATOR_PROVISIONING`" in text
    assert "`READY_FOR_PRODUCTION=FALSE`" in text
    assert "`EXTERNAL_RESOURCES_CREATED=FALSE`" in text
    assert "`PUSH_PERFORMED=FALSE`" in text
    assert "`BROKER_AUTHORITY=FALSE`" in text
    assert "`PAPER_AUTHORITY=FALSE`" in text
    assert "`LIVE_AUTHORITY=FALSE`" in text
    assert "`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`" in text
    assert "PROVISIONING_STATUS=READY_FOR_PRODUCTION" not in text
    assert "LIVE_AUTHORITY=TRUE" not in text


def test_report_records_validation_limits_and_unchanged_baselines():
    text = _report()

    assert "no native `fmt`, `validate`, `plan`, or `apply` was run" in text
    assert "160 inherited collection errors" in text
    assert "ARMS_MAXIMUM_QUOTE_AGE_SECONDS" in text
    assert text.count("**UNCHANGED**") == 5
