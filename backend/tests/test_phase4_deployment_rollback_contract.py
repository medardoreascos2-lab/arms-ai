"""R46D regression checks for the deployment rollback safety contract."""

from pathlib import Path


DOCUMENT = (
    Path(__file__).parents[1] / "phase4" / "DEPLOYMENT_ROLLBACK.md"
).read_text(encoding="utf-8")


def test_rollback_contract_has_all_required_operational_sections():
    for heading in (
        "## Safety declarations",
        "## Entry criteria",
        "## Previous application artifact",
        "## Compatible schema range",
        "## Feature flag rollback",
        "## Worker rollback",
        "## Application rollback procedure",
        "## Database restore escalation",
        "## Abort and escalation criteria",
        "## Completion evidence",
    ):
        assert heading in DOCUMENT


def test_application_and_database_rollback_are_explicitly_separate():
    assert "APPLICATION_ROLLBACK != DATABASE_ROLLBACK" in DOCUMENT
    assert "AUTOMATIC_REVERSE_MIGRATIONS: PROHIBITED" in DOCUMENT
    assert "DATABASE_RESTORE: MANUAL_ESCALATION_ONLY" in DOCUMENT
    assert "Application rollback never lowers the database schema version." in DOCUMENT
    assert "Never restore over an active database." in DOCUMENT


def test_rollback_keeps_execution_and_human_boundaries_fail_closed():
    assert "LIVE_TRADING_ENABLEMENT: OUT_OF_SCOPE" in DOCUMENT
    assert "OPERATOR_RELEASE_REQUIRED: TRUE" in DOCUMENT
    assert "state-changing operations blocked" in DOCUMENT
    assert "explicit operator release" in DOCUMENT
    assert "does not authorize a deployment" in DOCUMENT


def test_contract_requires_traceable_artifacts_schema_workers_and_backups():
    for evidence in (
        "full Git SHA",
        "manifest SHA",
        "every artifact hash",
        "declared compatible range",
        "before/after feature flags",
        "before/after worker generations",
        "isolated restore validation",
        "account, portfolio, journal, audit, outbox, and risk reconciliation",
    ):
        assert evidence in DOCUMENT


def test_document_contains_no_direct_deployment_or_destructive_commands():
    lowered = DOCUMENT.lower()
    for command in (
        "docker push",
        "docker run",
        "kubectl ",
        "terraform ",
        "git reset",
        "drop table",
        "alembic downgrade",
    ):
        assert command not in lowered
