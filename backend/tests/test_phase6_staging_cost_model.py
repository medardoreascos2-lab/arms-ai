"""R74C contract checks for the external staging cost model."""

from pathlib import Path
import re


ROOT = Path(__file__).parents[2]
DOCUMENT = ROOT / "docs" / "phase6" / "STAGING_COST_MODEL_R74C.md"


def _text() -> str:
    return DOCUMENT.read_text(encoding="utf-8")


def test_cost_model_has_all_classes_and_identifies_medium_baseline():
    text = _text()

    assert "## LOW" in text
    assert "## MEDIUM" in text
    assert "## HIGH" in text
    assert "`BASELINE_COST_CLASS=MEDIUM`" in text


def test_cost_model_lists_every_material_driver_without_exact_prices():
    text = _text()

    for driver in (
        "Compute",
        "PostgreSQL",
        "Network",
        "Logs and metrics",
        "Secrets and keys",
        "Backups",
        "Artifact registry",
        "Identity and alerts",
    ):
        assert f"| {driver} |" in text
    assert "`EXACT_PRICE_ESTIMATE=UNAVAILABLE`" in text
    assert re.search(r"[$€£]\s*\d", text) is None


def test_cost_model_requires_approval_and_preserves_authority_boundaries():
    text = _text()

    for token in (
        "COST_APPROVAL_REQUIRED=TRUE",
        "PURCHASE_PERFORMED=FALSE",
        "EXTERNAL_RESOURCES_CREATED=FALSE",
        "BROKER_AUTHORITY=FALSE",
        "PAPER_AUTHORITY=FALSE",
        "LIVE_AUTHORITY=FALSE",
        "PRODUCTION_DEPLOYMENT_AUTHORITY=FALSE",
    ):
        assert f"`{token}`" in text
