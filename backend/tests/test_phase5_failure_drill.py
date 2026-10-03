"""R60C combined synthetic failure drill tests."""

from dataclasses import replace
from pathlib import Path

import pytest

from backend.phase5 import (
    PHASE5_FAILURE_RECOVERY_SEQUENCE,
    Phase5FailureAction,
    Phase5FailureDrillStatus,
    Phase5FailureEvidence,
    Phase5SyntheticFailureDrill,
    render_phase5_failure_drill_runbook,
)


COMPLETE_EVIDENCE = Phase5FailureEvidence(
    database_outage_contained=True,
    worker_restart_verified=True,
    scheduler_failover_verified=True,
    auth_key_rotation_verified=True,
    queue_backlog_bounded=True,
    research_overload_throttled=True,
    backup_restore_verified=True,
    truthful_health_verified=True,
)


def test_combined_failure_drill_accepts_only_complete_evidence_in_documented_order():
    report = Phase5SyntheticFailureDrill.evaluate(
        COMPLETE_EVIDENCE,
        PHASE5_FAILURE_RECOVERY_SEQUENCE,
    )

    assert report.status is Phase5FailureDrillStatus.PASSED
    assert report.sequence_verified is True
    assert report.first_mismatch_index is None
    assert report.missing_evidence == ()
    assert report.operational_recovery_verified is False
    assert report.operator_release_granted is False
    assert report.external_effect_authorized is False
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert report.live_trading_authorized is False


@pytest.mark.parametrize(
    "field_name",
    [
        "database_outage_contained",
        "worker_restart_verified",
        "scheduler_failover_verified",
        "auth_key_rotation_verified",
        "queue_backlog_bounded",
        "research_overload_throttled",
        "backup_restore_verified",
        "truthful_health_verified",
    ],
)
def test_each_missing_recovery_evidence_fails_closed(field_name):
    evidence = replace(COMPLETE_EVIDENCE, **{field_name: False})

    report = Phase5SyntheticFailureDrill.evaluate(
        evidence,
        PHASE5_FAILURE_RECOVERY_SEQUENCE,
    )

    assert report.status is Phase5FailureDrillStatus.FAILED
    assert report.sequence_verified is True
    assert report.missing_evidence == (field_name,)
    assert report.execution_authorized is False
    assert report.external_effect_authorized is False


def test_reordered_missing_or_extra_recovery_steps_fail_sequence_verification():
    expected = PHASE5_FAILURE_RECOVERY_SEQUENCE
    variants = (
        expected[:-1],
        (expected[1], expected[0], *expected[2:]),
        expected + (Phase5FailureAction.ASSERT_SYNTHETIC_SCOPE,),
    )

    for observed in variants:
        report = Phase5SyntheticFailureDrill.evaluate(COMPLETE_EVIDENCE, observed)
        assert report.status is Phase5FailureDrillStatus.FAILED
        assert report.sequence_verified is False
        assert report.first_mismatch_index is not None
        assert report.operator_release_granted is False


def test_runbook_exactly_matches_executable_combined_recovery_order():
    path = Path(__file__).parents[2] / "docs" / "phase5" / "FAILURE_DRILL_R60C.md"

    assert path.read_text(encoding="utf-8") == render_phase5_failure_drill_runbook()


def test_recovery_order_blocks_first_and_requires_operator_release_last():
    assert PHASE5_FAILURE_RECOVERY_SEQUENCE[:3] == (
        Phase5FailureAction.ASSERT_SYNTHETIC_SCOPE,
        Phase5FailureAction.DECLARE_COMBINED_INCIDENT,
        Phase5FailureAction.BLOCK_EXECUTION_AND_MUTATIONS,
    )
    assert PHASE5_FAILURE_RECOVERY_SEQUENCE[-1] is (
        Phase5FailureAction.REQUIRE_OPERATOR_RELEASE
    )
