"""Deterministic Phase 5 gate for requesting external staging provisioning."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from enum import Enum


class Phase5StagingReleaseState(str, Enum):
    READY_FOR_EXTERNAL_STAGING_PROVISIONING = (
        "READY_FOR_EXTERNAL_STAGING_PROVISIONING"
    )
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"


REQUIRED_EXTERNAL_STAGING_BLOCKERS = (
    "POSTGRESQL_RUNTIME",
    "MANAGED_SECRET_PROVIDER",
    "EXTERNAL_IDENTITY_PROVIDER",
    "EXTERNAL_TELEMETRY_AND_ALERTING",
    "OFF_HOST_BACKUP_AND_MANAGED_KEYS",
    "ARTIFACT_REGISTRY_AND_SIGNING",
    "DNS_TLS_PRIVATE_NETWORK_AND_ORCHESTRATION",
)


@dataclass(frozen=True)
class Phase5StagingReleaseEvidence:
    local_staging_tests_green: bool
    security_review_complete: bool
    backup_restore_verified: bool
    api_replicas_verified: bool
    worker_replicas_verified: bool
    scheduler_replicas_verified: bool
    load_failover_verified: bool
    artifact_integrity_verified: bool
    v8_baseline_unchanged: bool
    published_phase_baselines_unchanged: bool
    execution_authority_present: bool = False
    broker_authority_present: bool = False
    paper_authority_present: bool = False
    live_authority_present: bool = False
    production_authority_present: bool = False
    deployment_authority_present: bool = False
    external_blockers: tuple[str, ...] = REQUIRED_EXTERNAL_STAGING_BLOCKERS

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if item.name == "external_blockers":
                continue
            if type(value) is not bool:
                raise ValueError(f"{item.name} must be bool")
        if self.external_blockers != REQUIRED_EXTERNAL_STAGING_BLOCKERS:
            raise ValueError(
                "external_blockers must disclose every known Phase 5 provider blocker"
            )


@dataclass(frozen=True)
class Phase5StagingReleaseResult:
    state: Phase5StagingReleaseState
    reasons: tuple[str, ...]
    external_blockers: tuple[str, ...]
    all_local_gates_passed: bool
    external_staging_provisioning_authorized: bool = field(
        default=False,
        init=False,
    )
    production_ready: bool = field(default=False, init=False)
    production_authorized: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    broker_authorized: bool = field(default=False, init=False)
    paper_trading_authorized: bool = field(default=False, init=False)
    live_trading_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.state, Phase5StagingReleaseState):
            raise ValueError("state must be Phase5StagingReleaseState")
        if not isinstance(self.reasons, tuple) or any(
            not isinstance(reason, str) or not reason for reason in self.reasons
        ):
            raise ValueError("reasons must contain non-empty strings")
        if self.external_blockers != REQUIRED_EXTERNAL_STAGING_BLOCKERS:
            raise ValueError("release result must retain every external blocker")
        if type(self.all_local_gates_passed) is not bool:
            raise ValueError("all_local_gates_passed must be bool")


_LOCAL_GATES = (
    ("local_staging_tests_green", "LOCAL_STAGING_TESTS_NOT_GREEN"),
    ("security_review_complete", "SECURITY_REVIEW_INCOMPLETE"),
    ("backup_restore_verified", "BACKUP_RESTORE_UNVERIFIED"),
    ("api_replicas_verified", "API_REPLICAS_UNVERIFIED"),
    ("worker_replicas_verified", "WORKER_REPLICAS_UNVERIFIED"),
    ("scheduler_replicas_verified", "SCHEDULER_REPLICAS_UNVERIFIED"),
    ("load_failover_verified", "LOAD_FAILOVER_UNVERIFIED"),
    ("artifact_integrity_verified", "ARTIFACT_INTEGRITY_UNVERIFIED"),
)
_BASELINE_GATES = (
    ("v8_baseline_unchanged", "V8_BASELINE_CHANGED"),
    ("published_phase_baselines_unchanged", "PUBLISHED_PHASE_BASELINE_CHANGED"),
)
_AUTHORITY_GATES = (
    ("execution_authority_present", "EXECUTION_AUTHORITY_PRESENT"),
    ("broker_authority_present", "BROKER_AUTHORITY_PRESENT"),
    ("paper_authority_present", "PAPER_AUTHORITY_PRESENT"),
    ("live_authority_present", "LIVE_AUTHORITY_PRESENT"),
    ("production_authority_present", "PRODUCTION_AUTHORITY_PRESENT"),
    ("deployment_authority_present", "DEPLOYMENT_AUTHORITY_PRESENT"),
)


class Phase5StagingReleaseGate:
    """Classify immutable evidence without provisioning or execution effects."""

    execution_authorized = False
    broker_authorized = False
    paper_trading_authorized = False
    live_trading_authorized = False
    production_ready = False
    production_authorized = False
    deployment_authorized = False
    external_staging_provisioning_authorized = False

    def evaluate(
        self,
        evidence: Phase5StagingReleaseEvidence,
    ) -> Phase5StagingReleaseResult:
        if not isinstance(evidence, Phase5StagingReleaseEvidence):
            raise ValueError("evidence must be Phase5StagingReleaseEvidence")

        blocked_reasons = tuple(
            reason
            for attribute, reason in (*_BASELINE_GATES, *_AUTHORITY_GATES)
            if (
                not getattr(evidence, attribute)
                if attribute.endswith("_unchanged")
                else getattr(evidence, attribute)
            )
        )
        hold_reasons = tuple(
            reason
            for attribute, reason in _LOCAL_GATES
            if not getattr(evidence, attribute)
        )
        all_local_gates_passed = not blocked_reasons and not hold_reasons

        if blocked_reasons:
            state = Phase5StagingReleaseState.BLOCKED
            reasons = blocked_reasons + hold_reasons
        elif hold_reasons:
            state = Phase5StagingReleaseState.HOLD
            reasons = hold_reasons
        else:
            state = (
                Phase5StagingReleaseState.READY_FOR_EXTERNAL_STAGING_PROVISIONING
            )
            reasons = ()

        return Phase5StagingReleaseResult(
            state=state,
            reasons=reasons,
            external_blockers=evidence.external_blockers,
            all_local_gates_passed=all_local_gates_passed,
        )
