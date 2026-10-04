"""R76A completeness checks for the external staging threat review."""

from pathlib import Path


ROOT = Path(__file__).parents[2]
DOCUMENT = ROOT / "docs" / "phase6" / "EXTERNAL_STAGING_THREAT_REVIEW_R76A.md"


def _text() -> str:
    return DOCUMENT.read_text(encoding="utf-8")


def test_threat_review_covers_all_required_external_threats():
    text = _text()

    for threat in (
        "Internet ingress",
        "Credential compromise",
        "Tenant breakout",
        "Secret exfiltration",
        "DB compromise",
        "Supply chain",
        "Artifact tampering",
        "Backup theft",
        "Identity forgery",
        "Worker takeover",
    ):
        assert f"| {threat} |" in text


def test_each_threat_has_control_detection_response_and_residual_gate_columns():
    text = _text()
    rows = [line for line in text.splitlines() if line.startswith("| ")]
    threat_rows = rows[2:]

    assert len(threat_rows) == 10
    assert all(len(row.split("|")) == 8 for row in threat_rows)
    assert all("|" in row and len(row) > 180 for row in threat_rows)


def test_review_preserves_unprovisioned_and_no_execution_boundaries():
    text = _text()

    for token in (
        "THREAT_REVIEW_STATUS=PASS_WITH_OPERATOR_ACTIONS",
        "EXTERNAL_RESOURCES_CREATED=FALSE",
        "PROVISIONING_AUTHORIZED=FALSE",
        "BROKER_AUTHORITY=FALSE",
        "PAPER_AUTHORITY=FALSE",
        "LIVE_AUTHORITY=FALSE",
        "PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE",
    ):
        assert f"`{token}`" in text
    assert "none has been provisioned" in " ".join(text.split())
