"""R45A tests for immutable service identities and credential references."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4.secret_providers import SecretMaterial, SecretReference
from backend.phase4.service_identity import (
    ServiceCredentialRotation,
    ServiceIdentity,
    ServicePermission,
    ServiceTenantScope,
)


ISSUED = datetime(2026, 10, 4, 2, 0, tzinfo=timezone.utc)


def identity(
    *,
    sequence=1,
    previous=None,
    permissions=frozenset({ServicePermission.HEALTH_READ}),
):
    return ServiceIdentity(
        service_id="phase4.health-reader",
        tenant_scope=ServiceTenantScope(frozenset({"tenant-a", "tenant-b"})),
        permissions=permissions,
        credential_reference=SecretReference(f"service/health/v{sequence}"),
        expires_at=ISSUED + timedelta(days=30),
        rotation=ServiceCredentialRotation(
            sequence,
            ISSUED,
            ISSUED + timedelta(days=20),
            previous,
        ),
    )


def test_service_identity_carries_explicit_scope_permission_reference_and_rotation():
    item = identity()
    assert item.service_id == "phase4.health-reader"
    assert item.tenant_scope.allows("tenant-a") is True
    assert item.tenant_scope.allows("tenant-c") is False
    assert item.covers(ServicePermission.HEALTH_READ, "tenant-a") is True
    assert item.covers(ServicePermission.METRICS_READ, "tenant-a") is False
    assert item.credential_reference.reference_id == "service/health/v1"
    assert item.live_trading_authorized is False
    assert item.execution_authorized is False


def test_expiry_and_rotation_windows_are_fail_closed_at_boundaries():
    item = identity()
    assert item.active_at(ISSUED - timedelta(microseconds=1)) is False
    assert item.active_at(ISSUED) is True
    assert item.rotation_due_at(ISSUED + timedelta(days=20)) is True
    assert item.active_at(ISSUED + timedelta(days=30)) is False
    assert item.rotation_due_at(ISSUED + timedelta(days=30)) is False


def test_rotated_identity_requires_distinct_previous_reference():
    previous = SecretReference("service/health/v1")
    item = identity(sequence=2, previous=previous)
    assert item.rotation.previous_credential_reference == previous
    with pytest.raises(ValueError, match="must differ"):
        ServiceIdentity(
            item.service_id,
            item.tenant_scope,
            item.permissions,
            previous,
            item.expires_at,
            item.rotation,
        )


def test_rotation_metadata_rejects_missing_or_unexpected_previous_reference():
    with pytest.raises(ValueError, match="initial"):
        ServiceCredentialRotation(1, ISSUED, ISSUED + timedelta(days=1), SecretReference("old"))
    with pytest.raises(ValueError, match="requires"):
        ServiceCredentialRotation(2, ISSUED, ISSUED + timedelta(days=1))
    with pytest.raises(ValueError, match="follow"):
        ServiceCredentialRotation(1, ISSUED, ISSUED)


def test_identity_rejects_empty_scope_permissions_and_secret_material():
    with pytest.raises(ValueError, match="nonempty"):
        ServiceTenantScope(frozenset())
    with pytest.raises(ValueError, match="nonempty"):
        identity(permissions=frozenset())
    with SecretMaterial("fake-local-secret") as material:
        with pytest.raises(ValueError, match="SecretReference"):
            ServiceIdentity(
                "phase4.invalid",
                ServiceTenantScope(frozenset({"tenant-a"})),
                frozenset({ServicePermission.HEALTH_READ}),
                material,
                ISSUED + timedelta(days=2),
                ServiceCredentialRotation(1, ISSUED, ISSUED + timedelta(days=1)),
            )


def test_permissions_contain_no_broker_or_live_trading_authority():
    values = {item.value for item in ServicePermission}
    assert not any("BROKER" in value or "LIVE" in value or "TRADE" in value for value in values)


def test_invalid_service_id_and_naive_times_fail_closed():
    valid = identity()
    with pytest.raises(ValueError, match="lowercase"):
        ServiceIdentity(
            "Phase4 Admin",
            valid.tenant_scope,
            valid.permissions,
            valid.credential_reference,
            valid.expires_at,
            valid.rotation,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        valid.active_at(ISSUED.replace(tzinfo=None))
