"""R77C operator provisioning plan contract tests."""

from pathlib import Path


PLAN = Path(__file__).parents[2] / "docs" / "phase6" / "OPERATOR_PROVISIONING_PLAN_R77C.md"


def _plan() -> str:
    return PLAN.read_text(encoding="utf-8")


def test_plan_classifies_every_required_external_action_category():
    text = _plan()

    for category in (
        "Creates external resources",
        "Incurs cost",
        "Requires credentials",
        "Modifies DNS/network",
        "Uploads artifacts",
    ):
        assert category in text
    assert "Gate 3: foundational provisioning" in text
    assert "Gate 5: artifact build and upload" in text
    assert "Gate 6: ingress, DNS, and workload deployment" in text


def test_plan_starts_with_every_operator_action_unexecuted():
    text = _plan()

    assert "Every checkbox is intentionally\nopen" in text
    assert "- [x]" not in text.lower()
    assert "`PLAN_EXECUTION_AUTHORIZED=FALSE`" in text
    assert "`EXTERNAL_ACTIONS_PERFORMED=FALSE`" in text
    assert "`PROVISIONING_REQUIRES_SEPARATE_APPROVAL=TRUE`" in text


def test_plan_never_grants_production_or_trading_authority():
    text = _plan()

    assert "`CURRENT_STATUS=READY_FOR_OPERATOR_PROVISIONING`" in text
    assert "`READY_FOR_PRODUCTION=FALSE`" in text
    assert "`BROKER_AUTHORITY=FALSE`" in text
    assert "`PAPER_AUTHORITY=FALSE`" in text
    assert "`LIVE_AUTHORITY=FALSE`" in text
    assert "`PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE`" in text
    assert "LIVE_AUTHORITY=TRUE" not in text
    assert "PRODUCTION_DEPLOYMENT_AUTHORITY=TRUE" not in text


def test_plan_keeps_nq_mnq_validation_synthetic_and_fail_closed():
    text = _plan()

    assert "Validate NQ and MNQ independently with approved synthetic datasets" in text
    assert "cause zero broker, order, position, portfolio, account, journal" in text
    assert "Restore only to a new isolated target" in text
