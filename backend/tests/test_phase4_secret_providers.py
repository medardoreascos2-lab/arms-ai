"""R41A tests for ephemeral, fail-closed secret provider contracts."""

from pathlib import Path

import pytest

from backend.phase4.secret_providers import (
    DisabledSecretProvider,
    EnvironmentSecretProvider,
    FileSecretProvider,
    FutureCloudSecretProvider,
    SecretMaterial,
    SecretMaterialClosedError,
    SecretNotFoundError,
    SecretProvider,
    SecretProviderError,
    SecretProviderUnavailableError,
    SecretReference,
)


REFERENCE = SecretReference("secrets/arms/staging/postgres")
FAKE_VALUE = "fake-local-test-value-41a"


def test_secret_reference_accepts_only_opaque_identifiers():
    assert REFERENCE.reference_id == "secrets/arms/staging/postgres"
    for invalid in (
        "",
        "postgresql://user:pass@host/db",
        "name=value",
        "space value",
        "@reference",
    ):
        with pytest.raises(ValueError, match="secret reference"):
            SecretReference(invalid)


def test_secret_material_is_redacted_and_zeroized_on_close():
    material = SecretMaterial(FAKE_VALUE)
    assert material.reveal() == FAKE_VALUE
    assert FAKE_VALUE not in repr(material)
    assert FAKE_VALUE not in str(material)
    buffer = material._buffer
    material.close()
    assert material.closed is True
    assert set(buffer) == {0}
    with pytest.raises(SecretMaterialClosedError, match="closed"):
        material.reveal()


def test_secret_material_context_manager_closes_after_ephemeral_use():
    material = SecretMaterial(FAKE_VALUE)
    with material as opened:
        assert opened.reveal() == FAKE_VALUE
    assert material.closed is True


def test_environment_provider_uses_hashed_reference_name_and_never_mutates_mapping():
    probe = EnvironmentSecretProvider(environment={})
    name = probe.environment_name(REFERENCE)
    environment = {name: FAKE_VALUE}
    before = dict(environment)
    provider = EnvironmentSecretProvider(environment=environment)
    with provider.resolve(REFERENCE) as material:
        assert material.reveal() == FAKE_VALUE
    assert environment == before
    assert REFERENCE.reference_id not in name
    assert provider.execution_authorized is False
    assert provider.production_mutation_authorized is False
    assert isinstance(provider, SecretProvider)


def test_environment_provider_fails_closed_for_missing_or_invalid_material():
    provider = EnvironmentSecretProvider(environment={})
    with pytest.raises(SecretNotFoundError, match="not configured"):
        provider.resolve(REFERENCE)
    name = provider.environment_name(REFERENCE)
    with pytest.raises(SecretProviderError, match="invalid") as error:
        EnvironmentSecretProvider(environment={name: ""}).resolve(REFERENCE)
    assert FAKE_VALUE not in str(error.value)


def test_file_provider_requires_explicit_local_test_mode_and_only_reads(tmp_path):
    root = tmp_path.resolve()
    with pytest.raises(SecretProviderUnavailableError, match="local-test"):
        FileSecretProvider(root)
    provider = FileSecretProvider(root, local_test_enabled=True)
    path = provider.path_for(REFERENCE)
    assert path.parent == root
    assert REFERENCE.reference_id not in path.name
    path.write_text(FAKE_VALUE + "\n", encoding="utf-8")
    before = path.read_bytes()
    with provider.resolve(REFERENCE) as material:
        assert material.reveal() == FAKE_VALUE
    assert path.read_bytes() == before
    assert provider.local_test_only is True
    assert provider.execution_authorized is False


def test_file_provider_rejects_missing_oversized_and_non_utf8_values(tmp_path):
    provider = FileSecretProvider(tmp_path.resolve(), local_test_enabled=True)
    path = provider.path_for(REFERENCE)
    with pytest.raises(SecretNotFoundError, match="not configured"):
        provider.resolve(REFERENCE)
    path.write_bytes(b"x" * (64 * 1024 + 1))
    with pytest.raises(SecretProviderError, match="size limit"):
        provider.resolve(REFERENCE)
    path.write_bytes(b"\xff")
    with pytest.raises(SecretProviderError, match="UTF-8"):
        provider.resolve(REFERENCE)


def test_disabled_and_future_cloud_providers_are_nonfunctional_seams():
    disabled = DisabledSecretProvider()
    with pytest.raises(SecretProviderUnavailableError, match="disabled"):
        disabled.resolve(REFERENCE)
    cloud = FutureCloudSecretProvider("future_cloud")
    with pytest.raises(SecretProviderUnavailableError, match="not implemented"):
        cloud.resolve(REFERENCE)
    assert cloud.execution_authorized is False
    assert cloud.production_mutation_authorized is False
    assert isinstance(disabled, SecretProvider)
    assert isinstance(cloud, SecretProvider)


def test_file_provider_root_must_already_exist(tmp_path):
    missing = Path(tmp_path) / "missing"
    with pytest.raises(SecretProviderUnavailableError, match="unavailable"):
        FileSecretProvider(missing.resolve(), local_test_enabled=True)
