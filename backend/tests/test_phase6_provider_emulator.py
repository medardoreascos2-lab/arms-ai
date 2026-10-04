"""R75A local-only emulation of selected external staging dependencies."""

from decimal import Decimal

import pytest

from backend.phase6.provider_emulator import (
    LocalProviderEmulator,
    ProviderDependency,
    ProviderDependencyUnavailable,
    ProviderEmulationError,
)


SECRET_REFERENCE = (
    "arn:aws:secretsmanager:phase6-local:000000000000:secret:"
    "arms-ai/staging/application-database"
)


def test_all_selected_external_dependencies_are_emulated_locally():
    emulator = LocalProviderEmulator()
    digest = "sha256:" + "a" * 64

    assert emulator.resolve_database_endpoint().startswith("emulator+postgresql://")
    secret = emulator.resolve_secret(SECRET_REFERENCE)
    identity = emulator.resolve_identity_metadata()
    metric = emulator.emit_metric("DatabaseHealth", Decimal("1"), {"environment": "staging"})
    artifact = emulator.resolve_artifact(digest)
    backup = emulator.store_backup("backups/synthetic/run-1.bin", b"synthetic-backup")

    assert secret.synthetic is True and secret.plaintext_exposed is False
    assert len(secret.material_fingerprint) == 64
    assert identity.issuer.endswith(".invalid/")
    assert identity.jwks_uri.endswith(".invalid/.well-known/jwks.json")
    assert metric in emulator.metrics
    assert artifact.endswith(digest)
    assert emulator.backups[backup.key] == backup
    assert backup.encrypted is True


def test_emulator_never_loads_credentials_calls_network_or_authorizes_execution():
    emulator = LocalProviderEmulator()

    emulator.resolve_database_endpoint()
    emulator.resolve_secret(SECRET_REFERENCE)
    emulator.resolve_identity_metadata()
    emulator.emit_metric("ApiHealth", Decimal("1"), {})
    emulator.resolve_artifact("sha256:" + "b" * 64)
    emulator.store_backup("backups/synthetic/test.bin", b"payload")

    assert emulator.credentials_loaded is False
    assert emulator.network_calls == 0
    assert emulator.external_mutations == 0
    assert emulator.execution_authorized is False


def test_secret_resolution_exposes_only_reference_version_and_fingerprint():
    emulator = LocalProviderEmulator()
    resolution = emulator.resolve_secret(SECRET_REFERENCE)

    assert set(vars(resolution)) == {
        "reference",
        "version",
        "material_fingerprint",
        "synthetic",
        "plaintext_exposed",
    }
    assert resolution.plaintext_exposed is False
    assert not hasattr(resolution, "value")
    with pytest.raises(ProviderEmulationError, match="synthetic reference"):
        emulator.resolve_secret("arn:aws:secretsmanager:us-east-1:123456789012:secret:real")


def test_emulator_rejects_unpinned_artifacts_unsafe_backups_and_secret_metric_labels():
    emulator = LocalProviderEmulator()

    with pytest.raises(ProviderEmulationError, match="sha256"):
        emulator.resolve_artifact("latest")
    with pytest.raises(ProviderEmulationError, match="backups prefix"):
        emulator.store_backup("outside/item", b"payload")
    with pytest.raises(ProviderEmulationError, match="secret-bearing"):
        emulator.emit_metric("Unsafe", Decimal("1"), {"secret_id": "value"})


@pytest.mark.parametrize("dependency", list(ProviderDependency))
def test_each_emulated_dependency_can_fail_closed(dependency):
    emulator = LocalProviderEmulator()
    emulator.set_available(dependency, False)

    calls = {
        ProviderDependency.DATABASE: emulator.resolve_database_endpoint,
        ProviderDependency.SECRETS: lambda: emulator.resolve_secret(SECRET_REFERENCE),
        ProviderDependency.IDENTITY: emulator.resolve_identity_metadata,
        ProviderDependency.METRICS: lambda: emulator.emit_metric("Health", Decimal("1"), {}),
        ProviderDependency.REGISTRY: lambda: emulator.resolve_artifact("sha256:" + "c" * 64),
        ProviderDependency.BACKUP: lambda: emulator.store_backup("backups/test.bin", b"data"),
    }
    with pytest.raises(ProviderDependencyUnavailable, match=dependency.value):
        calls[dependency]()

    assert emulator.credentials_loaded is False
    assert emulator.network_calls == 0
    assert emulator.external_mutations == 0
