"""Synthetic disaster recovery sequence drills with no recovery side effects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType


class DisasterScenario(str, Enum):
    DATABASE_CORRUPTION = "DATABASE_CORRUPTION"
    MISSING_WORKER = "MISSING_WORKER"
    PARTIAL_BACKUP = "PARTIAL_BACKUP"
    MIGRATION_FAILURE = "MIGRATION_FAILURE"


class RecoveryAction(str, Enum):
    ASSERT_SYNTHETIC_SCOPE = "ASSERT_SYNTHETIC_SCOPE"
    DECLARE_RECOVERY_REQUIRED = "DECLARE_RECOVERY_REQUIRED"
    BLOCK_EXECUTION_AND_MUTATIONS = "BLOCK_EXECUTION_AND_MUTATIONS"
    ISOLATE_CORRUPT_DATABASE = "ISOLATE_CORRUPT_DATABASE"
    SELECT_COMPLETED_BACKUP = "SELECT_COMPLETED_BACKUP"
    RESTORE_TO_ISOLATED_TEST = "RESTORE_TO_ISOLATED_TEST"
    VERIFY_CHECKSUMS_SCHEMA_TENANTS_ROWS = "VERIFY_CHECKSUMS_SCHEMA_TENANTS_ROWS"
    VERIFY_AUDIT_AND_RESEARCH = "VERIFY_AUDIT_AND_RESEARCH"
    RECONCILE_WORKERS_SCHEDULER_OUTBOX = "RECONCILE_WORKERS_SCHEDULER_OUTBOX"
    STOP_SCHEDULER_CLAIMS = "STOP_SCHEDULER_CLAIMS"
    EXPIRE_OR_RECONCILE_WORKER_LEASES = "EXPIRE_OR_RECONCILE_WORKER_LEASES"
    START_REPLACEMENT_WORKER_IN_TEST = "START_REPLACEMENT_WORKER_IN_TEST"
    VERIFY_QUEUE_AND_OUTBOX = "VERIFY_QUEUE_AND_OUTBOX"
    VERIFY_AGGREGATE_HEALTH = "VERIFY_AGGREGATE_HEALTH"
    QUARANTINE_INCOMPLETE_BACKUP = "QUARANTINE_INCOMPLETE_BACKUP"
    HALT_MIGRATIONS = "HALT_MIGRATIONS"
    INSPECT_SCHEMA_AND_MIGRATION_HISTORY = "INSPECT_SCHEMA_AND_MIGRATION_HISTORY"
    REQUIRE_OPERATOR_RELEASE = "REQUIRE_OPERATOR_RELEASE"


_PREFIX = (
    RecoveryAction.ASSERT_SYNTHETIC_SCOPE,
    RecoveryAction.DECLARE_RECOVERY_REQUIRED,
    RecoveryAction.BLOCK_EXECUTION_AND_MUTATIONS,
)


RECOVERY_SEQUENCES = MappingProxyType({
    DisasterScenario.DATABASE_CORRUPTION: _PREFIX + (
        RecoveryAction.ISOLATE_CORRUPT_DATABASE,
        RecoveryAction.SELECT_COMPLETED_BACKUP,
        RecoveryAction.RESTORE_TO_ISOLATED_TEST,
        RecoveryAction.VERIFY_CHECKSUMS_SCHEMA_TENANTS_ROWS,
        RecoveryAction.VERIFY_AUDIT_AND_RESEARCH,
        RecoveryAction.RECONCILE_WORKERS_SCHEDULER_OUTBOX,
        RecoveryAction.REQUIRE_OPERATOR_RELEASE,
    ),
    DisasterScenario.MISSING_WORKER: _PREFIX + (
        RecoveryAction.STOP_SCHEDULER_CLAIMS,
        RecoveryAction.EXPIRE_OR_RECONCILE_WORKER_LEASES,
        RecoveryAction.START_REPLACEMENT_WORKER_IN_TEST,
        RecoveryAction.VERIFY_QUEUE_AND_OUTBOX,
        RecoveryAction.VERIFY_AGGREGATE_HEALTH,
        RecoveryAction.REQUIRE_OPERATOR_RELEASE,
    ),
    DisasterScenario.PARTIAL_BACKUP: _PREFIX + (
        RecoveryAction.QUARANTINE_INCOMPLETE_BACKUP,
        RecoveryAction.SELECT_COMPLETED_BACKUP,
        RecoveryAction.RESTORE_TO_ISOLATED_TEST,
        RecoveryAction.VERIFY_CHECKSUMS_SCHEMA_TENANTS_ROWS,
        RecoveryAction.VERIFY_AUDIT_AND_RESEARCH,
        RecoveryAction.REQUIRE_OPERATOR_RELEASE,
    ),
    DisasterScenario.MIGRATION_FAILURE: _PREFIX + (
        RecoveryAction.HALT_MIGRATIONS,
        RecoveryAction.INSPECT_SCHEMA_AND_MIGRATION_HISTORY,
        RecoveryAction.SELECT_COMPLETED_BACKUP,
        RecoveryAction.RESTORE_TO_ISOLATED_TEST,
        RecoveryAction.VERIFY_CHECKSUMS_SCHEMA_TENANTS_ROWS,
        RecoveryAction.VERIFY_AUDIT_AND_RESEARCH,
        RecoveryAction.REQUIRE_OPERATOR_RELEASE,
    ),
})


class RecoveryDrillStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class SyntheticRecoveryIncident:
    scenario: DisasterScenario
    database_integrity_ok: bool
    worker_available: bool
    backup_complete: bool
    migration_succeeded: bool
    synthetic: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.scenario, DisasterScenario):
            raise ValueError("scenario must be a DisasterScenario")
        flags = {
            DisasterScenario.DATABASE_CORRUPTION: self.database_integrity_ok,
            DisasterScenario.MISSING_WORKER: self.worker_available,
            DisasterScenario.PARTIAL_BACKUP: self.backup_complete,
            DisasterScenario.MIGRATION_FAILURE: self.migration_succeeded,
        }
        if any(type(value) is not bool for value in flags.values()):
            raise ValueError("incident conditions must be boolean")
        if flags[self.scenario] is not False or any(
            value is not True for scenario, value in flags.items() if scenario is not self.scenario
        ):
            raise ValueError("incident must contain exactly its declared synthetic failure")

    @classmethod
    def for_scenario(cls, scenario: DisasterScenario) -> "SyntheticRecoveryIncident":
        if not isinstance(scenario, DisasterScenario):
            raise ValueError("scenario must be a DisasterScenario")
        values = {item: True for item in DisasterScenario}
        values[scenario] = False
        return cls(
            scenario,
            values[DisasterScenario.DATABASE_CORRUPTION],
            values[DisasterScenario.MISSING_WORKER],
            values[DisasterScenario.PARTIAL_BACKUP],
            values[DisasterScenario.MIGRATION_FAILURE],
        )


@dataclass(frozen=True)
class SyntheticRecoveryDrillResult:
    scenario: DisasterScenario
    status: RecoveryDrillStatus
    expected_actions: tuple[RecoveryAction, ...]
    observed_actions: tuple[RecoveryAction, ...]
    first_mismatch_index: int | None
    sequence_verified: bool
    operational_recovery_verified: bool = field(default=False, init=False)
    operator_release_granted: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


class SyntheticDisasterRecoveryDrill:
    execution_authorized = False
    production_mutation_authorized = False
    operational_recovery_verified = False

    @staticmethod
    def evaluate(
        incident: SyntheticRecoveryIncident,
        observed_actions: tuple[RecoveryAction, ...],
    ) -> SyntheticRecoveryDrillResult:
        if not isinstance(incident, SyntheticRecoveryIncident) or incident.synthetic is not True:
            raise ValueError("incident must be an explicitly synthetic recovery incident")
        if not isinstance(observed_actions, tuple) or any(
            not isinstance(item, RecoveryAction) for item in observed_actions
        ):
            raise ValueError("observed_actions must be an immutable recovery action tuple")
        expected = RECOVERY_SEQUENCES[incident.scenario]
        mismatch = next(
            (
                index
                for index in range(max(len(expected), len(observed_actions)))
                if index >= len(expected)
                or index >= len(observed_actions)
                or expected[index] is not observed_actions[index]
            ),
            None,
        )
        passed = mismatch is None
        return SyntheticRecoveryDrillResult(
            incident.scenario,
            RecoveryDrillStatus.PASSED if passed else RecoveryDrillStatus.FAILED,
            expected,
            observed_actions,
            mismatch,
            passed,
        )


def render_synthetic_recovery_runbook() -> str:
    lines = [
        "# ARMS AI Phase 4 synthetic disaster recovery runbook",
        "",
        "These drills validate sequence evidence only. They do not recover production,",
        "grant operator release, enable execution, or mutate a current store.",
        "",
    ]
    for scenario in DisasterScenario:
        lines.extend((f"## {scenario.value}", ""))
        lines.extend(
            f"{index}. `{action.value}`"
            for index, action in enumerate(RECOVERY_SEQUENCES[scenario], start=1)
        )
        lines.append("")
    return "\n".join(lines)
