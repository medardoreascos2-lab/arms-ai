"""R75C external provider failure rehearsal tests."""

import pytest

from backend.phase6.failure_rehearsal import FailureState, rehearse_provider_failure
from backend.phase6.provider_emulator import LocalProviderEmulator, ProviderDependency


@pytest.mark.parametrize(
    ("dependency", "reason"),
    [
        (ProviderDependency.DATABASE, "MANAGED_DATABASE_UNAVAILABLE"),
        (ProviderDependency.SECRETS, "SECRET_PROVIDER_UNAVAILABLE"),
        (ProviderDependency.IDENTITY, "IDENTITY_JWKS_UNAVAILABLE"),
    ],
)
def test_critical_provider_failures_block_service_and_all_new_work(dependency, reason):
    emulator = LocalProviderEmulator()
    outcome = rehearse_provider_failure(emulator, dependency)

    assert outcome.state is FailureState.BLOCKED
    assert outcome.reason == reason
    assert outcome.service_ready is False
    assert outcome.read_only_available is False
    assert outcome.new_work_allowed is False
    assert outcome.research_allowed is False
    assert outcome.deployment_allowed is False
    assert outcome.backup_allowed is False
    assert outcome.execution_authorized is False


def test_telemetry_failure_degrades_to_read_only_and_pauses_new_work():
    outcome = rehearse_provider_failure(LocalProviderEmulator(), ProviderDependency.METRICS)

    assert outcome.state is FailureState.DEGRADED
    assert outcome.reason == "TELEMETRY_UNAVAILABLE_PAUSE_NEW_WORK"
    assert outcome.service_ready is False
    assert outcome.read_only_available is True
    assert outcome.new_work_allowed is False
    assert outcome.research_allowed is False
    assert outcome.deployment_allowed is False
    assert outcome.backup_allowed is True
    assert outcome.execution_authorized is False


def test_backup_failure_holds_release_and_backup_but_preserves_bounded_service():
    outcome = rehearse_provider_failure(LocalProviderEmulator(), ProviderDependency.BACKUP)

    assert outcome.state is FailureState.DEGRADED
    assert outcome.reason == "BACKUP_TARGET_UNAVAILABLE_HOLD_RELEASE"
    assert outcome.read_only_available is True
    assert outcome.new_work_allowed is True
    assert outcome.backup_allowed is False
    assert outcome.deployment_allowed is False
    assert outcome.research_allowed is False
    assert outcome.execution_authorized is False


def test_registry_failure_holds_deployment_without_claiming_running_service_ready():
    outcome = rehearse_provider_failure(LocalProviderEmulator(), ProviderDependency.REGISTRY)

    assert outcome.state is FailureState.DEGRADED
    assert outcome.reason == "ARTIFACT_REGISTRY_UNAVAILABLE_HOLD_DEPLOYMENT"
    assert outcome.service_ready is False
    assert outcome.read_only_available is True
    assert outcome.deployment_allowed is False
    assert outcome.backup_allowed is True
    assert outcome.execution_authorized is False


@pytest.mark.parametrize("dependency", list(ProviderDependency))
def test_every_rehearsal_has_zero_external_or_execution_side_effects(dependency):
    emulator = LocalProviderEmulator()
    outcome = rehearse_provider_failure(emulator, dependency)

    assert outcome.external_side_effects_attempted is False
    assert outcome.execution_authorized is False
    assert emulator.credentials_loaded is False
    assert emulator.network_calls == 0
    assert emulator.external_mutations == 0
    assert emulator.execution_authorized is False
