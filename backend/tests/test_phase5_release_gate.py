"""R63A deterministic Phase 5 external-staging release gate tests."""

from dataclasses import replace

import pytest

from backend.phase5 import (
    REQUIRED_EXTERNAL_STAGING_BLOCKERS,
    Phase5StagingReleaseEvidence,
    Phase5StagingReleaseGate,
    Phase5StagingReleaseState,
)


def _complete_evidence(**changes) -> Phase5StagingReleaseEvidence:
    evidence = Phase5StagingReleaseEvidence(
        local_staging_tests_green=True,
        security_review_complete=True,
        backup_restore_verified=True,
        api_replicas_verified=True,
        worker_replicas_verified=True,
        scheduler_replicas_verified=True,
        load_failover_verified=True,
        artifact_integrity_verified=True,
        v8_baseline_unchanged=True,
        published_phase_baselines_unchanged=True,
    )
    return replace(evidence, **changes)


def _assert_zero_authority(value) -> None:
    for attribute in (
        "external_staging_provisioning_authorized",
        "production_ready",
        "production_authorized",
        "deployment_authorized",
        "execution_authorized",
        "broker_authorized",
        "paper_trading_authorized",
        "live_trading_authorized",
    ):
        assert getattr(value, attribute) is False


def test_complete_local_evidence_is_ready_only_to_request_external_staging():
    result = Phase5StagingReleaseGate().evaluate(_complete_evidence())

    assert result.state is (
        Phase5StagingReleaseState.READY_FOR_EXTERNAL_STAGING_PROVISIONING
    )
    assert result.reasons == ()
    assert result.all_local_gates_passed is True
    assert result.external_blockers == REQUIRED_EXTERNAL_STAGING_BLOCKERS
    _assert_zero_authority(result)
    _assert_zero_authority(Phase5StagingReleaseGate())


@pytest.mark.parametrize(
    ("attribute", "reason"),
    (
        ("local_staging_tests_green", "LOCAL_STAGING_TESTS_NOT_GREEN"),
        ("security_review_complete", "SECURITY_REVIEW_INCOMPLETE"),
        ("backup_restore_verified", "BACKUP_RESTORE_UNVERIFIED"),
        ("api_replicas_verified", "API_REPLICAS_UNVERIFIED"),
        ("worker_replicas_verified", "WORKER_REPLICAS_UNVERIFIED"),
        ("scheduler_replicas_verified", "SCHEDULER_REPLICAS_UNVERIFIED"),
        ("load_failover_verified", "LOAD_FAILOVER_UNVERIFIED"),
        ("artifact_integrity_verified", "ARTIFACT_INTEGRITY_UNVERIFIED"),
    ),
)
def test_incomplete_local_requirement_holds_without_authority(attribute, reason):
    result = Phase5StagingReleaseGate().evaluate(
        _complete_evidence(**{attribute: False})
    )

    assert result.state is Phase5StagingReleaseState.HOLD
    assert result.reasons == (reason,)
    assert result.all_local_gates_passed is False
    _assert_zero_authority(result)


@pytest.mark.parametrize(
    ("attribute", "reason"),
    (
        ("v8_baseline_unchanged", "V8_BASELINE_CHANGED"),
        (
            "published_phase_baselines_unchanged",
            "PUBLISHED_PHASE_BASELINE_CHANGED",
        ),
        ("execution_authority_present", "EXECUTION_AUTHORITY_PRESENT"),
        ("broker_authority_present", "BROKER_AUTHORITY_PRESENT"),
        ("paper_authority_present", "PAPER_AUTHORITY_PRESENT"),
        ("live_authority_present", "LIVE_AUTHORITY_PRESENT"),
        ("production_authority_present", "PRODUCTION_AUTHORITY_PRESENT"),
        ("deployment_authority_present", "DEPLOYMENT_AUTHORITY_PRESENT"),
    ),
)
def test_baseline_or_authority_violation_blocks(attribute, reason):
    unsafe_value = not attribute.endswith("_unchanged")
    result = Phase5StagingReleaseGate().evaluate(
        _complete_evidence(**{attribute: unsafe_value})
    )

    assert result.state is Phase5StagingReleaseState.BLOCKED
    assert result.reasons == (reason,)
    assert result.all_local_gates_passed is False
    _assert_zero_authority(result)


def test_blocked_state_takes_precedence_and_reports_all_failures_in_stable_order():
    result = Phase5StagingReleaseGate().evaluate(
        _complete_evidence(
            local_staging_tests_green=False,
            v8_baseline_unchanged=False,
            live_authority_present=True,
        )
    )

    assert result.state is Phase5StagingReleaseState.BLOCKED
    assert result.reasons == (
        "V8_BASELINE_CHANGED",
        "LIVE_AUTHORITY_PRESENT",
        "LOCAL_STAGING_TESTS_NOT_GREEN",
    )
    _assert_zero_authority(result)


def test_gate_exposes_only_the_three_allowed_states():
    assert tuple(state.value for state in Phase5StagingReleaseState) == (
        "READY_FOR_EXTERNAL_STAGING_PROVISIONING",
        "HOLD",
        "BLOCKED",
    )


def test_evidence_rejects_truthy_non_boolean_and_hidden_external_blockers():
    with pytest.raises(ValueError, match="must be bool"):
        _complete_evidence(local_staging_tests_green="yes")

    with pytest.raises(ValueError, match="every known"):
        _complete_evidence(external_blockers=())


def test_gate_rejects_untyped_evidence_without_side_effects():
    gate = Phase5StagingReleaseGate()

    with pytest.raises(ValueError, match="Phase5StagingReleaseEvidence"):
        gate.evaluate({"local_staging_tests_green": True})

    _assert_zero_authority(gate)
