"""R97C final integration report contract tests."""

from pathlib import Path


REPORT = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "phase7"
    / "PHASE7_FINAL_INTEGRATION_R97C.md"
)


def test_phase7_final_report_records_required_scope_and_safe_final_state():
    text = REPORT.read_text(encoding="utf-8")

    required_sections = (
        "## Architecture",
        "## Cognitive core",
        "## Agents",
        "## Model routing",
        "## Tool routing",
        "## Memory interfaces",
        "## Financial routing",
        "### NQ and MNQ",
        "### Crypto arbitrage seam",
        "## Marketing and business",
        "## Life advisory",
        "## Rosita seam",
        "## Computer permissions",
        "## Tests",
        "## Security review",
        "## Remaining blockers",
    )

    assert all(section in text for section in required_sections)
    assert (
        "COGNITIVE_CORE_STATUS="
        "MEDAR_COGNITIVE_CORE_READY_FOR_MODEL_AND_MEMORY_INTEGRATION"
    ) in text
    assert "`PRODUCTION_AUTONOMY=FALSE`" in text
    assert "`BROKER_AUTHORITY=FALSE`" in text
    assert "`PAPER_AUTHORITY=FALSE`" in text
    assert "`LIVE_AUTHORITY=FALSE`" in text
    assert "`PUSH_PERFORMED=FALSE`" in text


def test_phase7_final_report_does_not_emit_production_autonomy_readiness():
    text = REPORT.read_text(encoding="utf-8")

    forbidden_assignment = "COGNITIVE_CORE_STATUS=" + "READY_FOR_PRODUCTION_AUTONOMY"
    assert forbidden_assignment not in text
