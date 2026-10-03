"""Combined synthetic Phase 5 failure drill and exact recovery-order contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Phase5FailureAction(str, Enum):
    ASSERT_SYNTHETIC_SCOPE = "ASSERT_SYNTHETIC_SCOPE"
    DECLARE_COMBINED_INCIDENT = "DECLARE_COMBINED_INCIDENT"
    BLOCK_EXECUTION_AND_MUTATIONS = "BLOCK_EXECUTION_AND_MUTATIONS"
    CONTAIN_DATABASE_OUTAGE = "CONTAIN_DATABASE_OUTAGE"
    QUIESCE_AND_RESTART_WORKER = "QUIESCE_AND_RESTART_WORKER"
    FAIL_OVER_SCHEDULER_LEASE = "FAIL_OVER_SCHEDULER_LEASE"
    ROTATE_AUTH_CREDENTIAL_REFERENCE = "ROTATE_AUTH_CREDENTIAL_REFERENCE"
    BOUND_QUEUE_BACKLOG = "BOUND_QUEUE_BACKLOG"
    THROTTLE_RESEARCH_OVERLOAD = "THROTTLE_RESEARCH_OVERLOAD"
    SELECT_VERIFIED_BACKUP = "SELECT_VERIFIED_BACKUP"
    RESTORE_TO_ISOLATED_DESTINATION = "RESTORE_TO_ISOLATED_DESTINATION"
    VERIFY_HASH_SCHEMA_AUDIT_TENANTS_PROVENANCE = (
        "VERIFY_HASH_SCHEMA_AUDIT_TENANTS_PROVENANCE"
    )
    RECONCILE_WORKERS_SCHEDULER_QUEUE = "RECONCILE_WORKERS_SCHEDULER_QUEUE"
    VERIFY_TRUTHFUL_BLOCKED_HEALTH = "VERIFY_TRUTHFUL_BLOCKED_HEALTH"
    REQUIRE_OPERATOR_RELEASE = "REQUIRE_OPERATOR_RELEASE"


PHASE5_FAILURE_RECOVERY_SEQUENCE = tuple(Phase5FailureAction)


class Phase5FailureDrillStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class Phase5FailureEvidence:
    database_outage_contained: bool
    worker_restart_verified: bool
    scheduler_failover_verified: bool
    auth_key_rotation_verified: bool
    queue_backlog_bounded: bool
    research_overload_throttled: bool
    backup_restore_verified: bool
    truthful_health_verified: bool
    synthetic: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for name, value in self.__dict__.items()
            if name != "synthetic"
        ):
            raise ValueError("failure evidence fields must be boolean")


@dataclass(frozen=True)
class Phase5FailureDrillReport:
    status: Phase5FailureDrillStatus
    expected_actions: tuple[Phase5FailureAction, ...]
    observed_actions: tuple[Phase5FailureAction, ...]
    sequence_verified: bool
    first_mismatch_index: int | None
    missing_evidence: tuple[str, ...]
    operational_recovery_verified: bool = field(default=False, init=False)
    operator_release_granted: bool = field(default=False, init=False)
    external_effect_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)


class Phase5SyntheticFailureDrill:
    """Evaluates evidence and order; it performs no recovery or external action."""

    operational_recovery_verified = False
    operator_release_granted = False
    external_effect_authorized = False
    execution_authorized = False
    production_mutation_authorized = False
    live_trading_authorized = False

    @staticmethod
    def evaluate(
        evidence: Phase5FailureEvidence,
        observed_actions: tuple[Phase5FailureAction, ...],
    ) -> Phase5FailureDrillReport:
        if not isinstance(evidence, Phase5FailureEvidence) or not evidence.synthetic:
            raise ValueError("evidence must describe an explicitly synthetic drill")
        if not isinstance(observed_actions, tuple) or any(
            not isinstance(item, Phase5FailureAction) for item in observed_actions
        ):
            raise ValueError("observed_actions must be an immutable action tuple")
        expected = PHASE5_FAILURE_RECOVERY_SEQUENCE
        mismatch = next(
            (
                index
                for index in range(max(len(expected), len(observed_actions)))
                if index >= len(expected)
                or index >= len(observed_actions)
                or observed_actions[index] is not expected[index]
            ),
            None,
        )
        missing = tuple(sorted(
            name
            for name, value in evidence.__dict__.items()
            if name != "synthetic" and value is not True
        ))
        passed = mismatch is None and not missing
        return Phase5FailureDrillReport(
            status=(
                Phase5FailureDrillStatus.PASSED
                if passed else Phase5FailureDrillStatus.FAILED
            ),
            expected_actions=expected,
            observed_actions=observed_actions,
            sequence_verified=mismatch is None,
            first_mismatch_index=mismatch,
            missing_evidence=missing,
        )


def render_phase5_failure_drill_runbook() -> str:
    lines = [
        "# Phase 5 synthetic combined failure drill (R60C)",
        "",
        "This exact order covers a synthetic database outage, worker crash, scheduler",
        "failover, authentication key rotation, queue backlog, research overload, and",
        "isolated backup restore. It grants no external, production, execution, broker,",
        "PAPER, or LIVE authority. Health remains blocked pending operator release.",
        "",
        "## Recovery order",
        "",
    ]
    lines.extend(
        f"{index}. `{action.value}`"
        for index, action in enumerate(PHASE5_FAILURE_RECOVERY_SEQUENCE, start=1)
    )
    lines.extend((
        "",
        "A missing, reordered, or additional action fails the drill. Each of the eight",
        "evidence checks must pass independently. Sequence success is test evidence only;",
        "it never proves production recovery or grants operator release.",
        "",
    ))
    return "\n".join(lines)
