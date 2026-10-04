"""Fail-closed Phase 6 rehearsal for emulated external provider outages."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from backend.phase6.provider_emulator import (
    LocalProviderEmulator,
    ProviderDependency,
    ProviderDependencyUnavailable,
)


class FailureState(str, Enum):
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True)
class ProviderFailureOutcome:
    dependency: ProviderDependency
    state: FailureState
    reason: str
    service_ready: bool
    read_only_available: bool
    new_work_allowed: bool
    research_allowed: bool
    deployment_allowed: bool
    backup_allowed: bool
    execution_authorized: bool = False
    external_side_effects_attempted: bool = False


_OUTCOMES = {
    ProviderDependency.DATABASE: ProviderFailureOutcome(
        ProviderDependency.DATABASE,
        FailureState.BLOCKED,
        "MANAGED_DATABASE_UNAVAILABLE",
        service_ready=False,
        read_only_available=False,
        new_work_allowed=False,
        research_allowed=False,
        deployment_allowed=False,
        backup_allowed=False,
    ),
    ProviderDependency.SECRETS: ProviderFailureOutcome(
        ProviderDependency.SECRETS,
        FailureState.BLOCKED,
        "SECRET_PROVIDER_UNAVAILABLE",
        service_ready=False,
        read_only_available=False,
        new_work_allowed=False,
        research_allowed=False,
        deployment_allowed=False,
        backup_allowed=False,
    ),
    ProviderDependency.IDENTITY: ProviderFailureOutcome(
        ProviderDependency.IDENTITY,
        FailureState.BLOCKED,
        "IDENTITY_JWKS_UNAVAILABLE",
        service_ready=False,
        read_only_available=False,
        new_work_allowed=False,
        research_allowed=False,
        deployment_allowed=False,
        backup_allowed=False,
    ),
    ProviderDependency.METRICS: ProviderFailureOutcome(
        ProviderDependency.METRICS,
        FailureState.DEGRADED,
        "TELEMETRY_UNAVAILABLE_PAUSE_NEW_WORK",
        service_ready=False,
        read_only_available=True,
        new_work_allowed=False,
        research_allowed=False,
        deployment_allowed=False,
        backup_allowed=True,
    ),
    ProviderDependency.BACKUP: ProviderFailureOutcome(
        ProviderDependency.BACKUP,
        FailureState.DEGRADED,
        "BACKUP_TARGET_UNAVAILABLE_HOLD_RELEASE",
        service_ready=False,
        read_only_available=True,
        new_work_allowed=True,
        research_allowed=False,
        deployment_allowed=False,
        backup_allowed=False,
    ),
    ProviderDependency.REGISTRY: ProviderFailureOutcome(
        ProviderDependency.REGISTRY,
        FailureState.DEGRADED,
        "ARTIFACT_REGISTRY_UNAVAILABLE_HOLD_DEPLOYMENT",
        service_ready=False,
        read_only_available=True,
        new_work_allowed=True,
        research_allowed=False,
        deployment_allowed=False,
        backup_allowed=True,
    ),
}


def _probe(emulator: LocalProviderEmulator, dependency: ProviderDependency) -> None:
    probes = {
        ProviderDependency.DATABASE: emulator.resolve_database_endpoint,
        ProviderDependency.SECRETS: lambda: emulator.resolve_secret(
            "arn:aws:secretsmanager:phase6-local:000000000000:secret:"
            "arms-ai/staging/application-database"
        ),
        ProviderDependency.IDENTITY: emulator.resolve_identity_metadata,
        ProviderDependency.METRICS: lambda: emulator.emit_metric(
            "FailureRehearsal", Decimal("1"), {"environment": "staging"}
        ),
        ProviderDependency.REGISTRY: lambda: emulator.resolve_artifact("sha256:" + "e" * 64),
        ProviderDependency.BACKUP: lambda: emulator.store_backup(
            "backups/rehearsal/probe.bin", b"synthetic-probe"
        ),
    }
    probes[dependency]()


def rehearse_provider_failure(
    emulator: LocalProviderEmulator,
    dependency: ProviderDependency,
) -> ProviderFailureOutcome:
    """Inject one outage, confirm denial, and return the required safe state."""

    if not isinstance(emulator, LocalProviderEmulator):
        raise TypeError("failure rehearsal requires LocalProviderEmulator")
    if not isinstance(dependency, ProviderDependency):
        raise TypeError("dependency must be ProviderDependency")
    emulator.set_available(dependency, False)
    try:
        _probe(emulator, dependency)
    except ProviderDependencyUnavailable:
        outcome = _OUTCOMES[dependency]
    else:
        raise AssertionError("unavailable dependency accepted a probe")
    if emulator.credentials_loaded or emulator.network_calls or emulator.external_mutations:
        raise AssertionError("failure rehearsal crossed the local emulation boundary")
    if emulator.execution_authorized:
        raise AssertionError("failure rehearsal granted execution authority")
    return outcome
