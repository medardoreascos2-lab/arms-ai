"""R52B local staging-secret rehearsal with synthetic in-memory values only.

The scoped harness in this test composes Phase 4 provider, service identity,
ephemeral material, and redaction contracts. It is not an external provider.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4.secret_providers import (
    EnvironmentSecretProvider,
    SecretNotFoundError,
    SecretProviderError,
    SecretReference,
)
from backend.phase4.secret_redaction import REDACTED, SecretRedactor
from backend.phase4.service_identity import (
    ServiceCredentialRotation,
    ServiceIdentity,
    ServicePermission,
    ServiceTenantScope,
)


NOW = datetime(2026, 10, 3, 23, 0, tzinfo=timezone.utc)
SYNTHETIC_V1 = "synthetic-r52b-worker-value-v1"
SYNTHETIC_V2 = "synthetic-r52b-worker-value-v2"
WORKER_V1 = SecretReference("secrets/arms/staging/worker/v1")
WORKER_V2 = SecretReference("secrets/arms/staging/worker/v2")
BACKUP_V1 = SecretReference("secrets/arms/staging/backup/v1")


class SecretScopeError(SecretProviderError):
    pass


@dataclass(frozen=True)
class SyntheticDescriptor:
    reference: SecretReference
    environment: str
    purpose: str
    version: int
    issued_at: datetime
    rotate_after: datetime
    expires_at: datetime
    service_id: str
    permission: ServicePermission
    tenant_scope: frozenset[str]
    previous_reference: SecretReference | None = None
    revoked: bool = False


class CountingProvider:
    provider_id = "synthetic_memory"
    local_test_only = True
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, values):
        probe = EnvironmentSecretProvider(environment={})
        environment = {
            probe.environment_name(reference): value
            for reference, value in values.items()
        }
        self._provider = EnvironmentSecretProvider(environment=environment)
        self.resolve_calls = []

    def resolve(self, reference):
        self.resolve_calls.append(reference)
        return self._provider.resolve(reference)


class ScopedSecretRehearsal:
    execution_authorized = False
    production_mutation_authorized = False
    live_trading_authorized = False

    def __init__(self, provider, descriptors, active_by_purpose):
        self.provider = provider
        self.descriptors = dict(descriptors)
        self.active_by_purpose = dict(active_by_purpose)

    def activate(self, purpose, replacement, *, now):
        descriptor = self.descriptors.get(replacement)
        current = self.active_by_purpose.get(purpose)
        if descriptor is None or descriptor.purpose != purpose:
            raise SecretScopeError("secret rotation is invalid")
        if descriptor.previous_reference != current:
            raise SecretScopeError("secret rotation lineage is invalid")
        if not descriptor.issued_at <= now < descriptor.expires_at:
            raise SecretScopeError("secret rotation is outside its active window")
        self.active_by_purpose[purpose] = replacement

    def resolve(self, purpose, identity, tenant_id, *, now, reference=None):
        current = self.active_by_purpose.get(purpose)
        selected = reference or current
        descriptor = self.descriptors.get(selected)
        if descriptor is None:
            raise SecretNotFoundError("staging secret metadata is not configured")
        if selected != current:
            current_descriptor = self.descriptors.get(current)
            if (
                current_descriptor is None
                or current_descriptor.previous_reference != selected
            ):
                raise SecretScopeError("staging secret version is not active")
        if descriptor.environment != "staging" or descriptor.purpose != purpose:
            raise SecretScopeError("staging secret scope is invalid")
        if descriptor.revoked or not descriptor.issued_at <= now < descriptor.expires_at:
            raise SecretScopeError("staging secret is inactive")
        if not isinstance(identity, ServiceIdentity) or not identity.active_at(now):
            raise SecretScopeError("service identity is inactive")
        if identity.service_id != descriptor.service_id:
            raise SecretScopeError("service identity is not authorized")
        if tenant_id not in descriptor.tenant_scope:
            raise SecretScopeError("tenant scope is not authorized")
        if not identity.covers(descriptor.permission, tenant_id):
            raise SecretScopeError("service permission is not authorized")
        return self.provider.resolve(descriptor.reference)


def _identity(
    service_id="phase5.worker",
    *,
    permission=ServicePermission.WORKER_SUPERVISE,
    tenants=frozenset({"tenant-a"}),
    expires_at=NOW + timedelta(days=30),
):
    issued_at = NOW - timedelta(days=2)
    rotate_after = min(NOW + timedelta(days=20), expires_at - timedelta(days=1))
    return ServiceIdentity(
        service_id=service_id,
        tenant_scope=ServiceTenantScope(tenants),
        permissions=frozenset({permission}),
        credential_reference=SecretReference(f"service/{service_id}/credential/v1"),
        expires_at=expires_at,
        rotation=ServiceCredentialRotation(
            sequence=1,
            issued_at=issued_at,
            rotate_after=rotate_after,
        ),
    )


def _descriptor(
    reference=WORKER_V1,
    *,
    version=1,
    previous=None,
    purpose="worker_transport",
    service_id="phase5.worker",
    permission=ServicePermission.WORKER_SUPERVISE,
    tenant_scope=frozenset({"tenant-a"}),
    issued_at=NOW - timedelta(hours=1),
    rotate_after=NOW + timedelta(days=5),
    expires_at=NOW + timedelta(days=10),
    revoked=False,
):
    return SyntheticDescriptor(
        reference=reference,
        environment="staging",
        purpose=purpose,
        version=version,
        issued_at=issued_at,
        rotate_after=rotate_after,
        expires_at=expires_at,
        service_id=service_id,
        permission=permission,
        tenant_scope=tenant_scope,
        previous_reference=previous,
        revoked=revoked,
    )


def _rehearsal(*descriptors, values=None, active=WORKER_V1):
    configured = descriptors or (_descriptor(),)
    provider = CountingProvider(values or {WORKER_V1: SYNTHETIC_V1})
    return provider, ScopedSecretRehearsal(
        provider,
        ((item.reference, item) for item in configured),
        {"worker_transport": active},
    )


def test_load_by_opaque_reference_returns_ephemeral_zeroized_material():
    provider, rehearsal = _rehearsal()

    material = rehearsal.resolve(
        "worker_transport", _identity(), "tenant-a", now=NOW
    )
    buffer = material._buffer
    with material as opened:
        assert opened.reveal() == SYNTHETIC_V1
        assert SYNTHETIC_V1 not in str(opened)
        assert SYNTHETIC_V1 not in repr(opened)

    assert material.closed is True
    assert set(buffer) == {0}
    assert provider.resolve_calls == [WORKER_V1]
    assert rehearsal.execution_authorized is False
    assert rehearsal.live_trading_authorized is False


def test_rotation_switches_to_new_immutable_reference_and_keeps_bounded_overlap():
    first = _descriptor(
        rotate_after=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
    )
    second = _descriptor(
        WORKER_V2,
        version=2,
        previous=WORKER_V1,
        issued_at=NOW - timedelta(minutes=1),
    )
    provider, rehearsal = _rehearsal(
        first,
        second,
        values={WORKER_V1: SYNTHETIC_V1, WORKER_V2: SYNTHETIC_V2},
    )

    rehearsal.activate("worker_transport", WORKER_V2, now=NOW)
    with rehearsal.resolve(
        "worker_transport", _identity(), "tenant-a", now=NOW
    ) as current:
        assert current.reveal() == SYNTHETIC_V2
    with rehearsal.resolve(
        "worker_transport",
        _identity(),
        "tenant-a",
        now=NOW,
        reference=WORKER_V1,
    ) as previous:
        assert previous.reveal() == SYNTHETIC_V1

    assert provider.resolve_calls == [WORKER_V2, WORKER_V1]


def test_missing_secret_fails_closed_with_no_material_or_authority():
    provider, rehearsal = _rehearsal(values={BACKUP_V1: "synthetic-unused"})

    with pytest.raises(SecretNotFoundError, match="not configured") as error:
        rehearsal.resolve("worker_transport", _identity(), "tenant-a", now=NOW)

    assert SYNTHETIC_V1 not in str(error.value)
    assert provider.resolve_calls == [WORKER_V1]
    assert rehearsal.execution_authorized is False
    assert rehearsal.production_mutation_authorized is False


@pytest.mark.parametrize(
    "descriptor, identity",
    (
        (_descriptor(expires_at=NOW, rotate_after=NOW - timedelta(minutes=1)), _identity()),
        (_descriptor(revoked=True), _identity()),
        (_descriptor(), _identity(expires_at=NOW)),
    ),
)
def test_expired_revoked_or_inactive_identity_denies_before_provider(
    descriptor, identity
):
    provider, rehearsal = _rehearsal(descriptor)

    with pytest.raises(SecretScopeError):
        rehearsal.resolve("worker_transport", identity, "tenant-a", now=NOW)

    assert provider.resolve_calls == []


def test_synthetic_value_is_redacted_from_operational_channels_and_errors():
    _, rehearsal = _rehearsal()
    redactor = SecretRedactor()
    with rehearsal.resolve(
        "worker_transport", _identity(), "tenant-a", now=NOW
    ) as material:
        value = material.reveal()
        records = (
            redactor.log(f"token={value}", {"secret": value}),
            redactor.audit({"credential": value}),
            redactor.exception(RuntimeError(f"password={value}")),
            redactor.worker_failure("worker_a", RuntimeError(f"api_key={value}")),
        )

    for record in records:
        assert SYNTHETIC_V1 not in repr(record)
        assert REDACTED in repr(record)


@pytest.mark.parametrize(
    "identity, tenant_id",
    (
        (_identity(service_id="phase5.backup"), "tenant-a"),
        (_identity(permission=ServicePermission.LOCAL_BACKUP_CREATE), "tenant-a"),
        (_identity(tenants=frozenset({"tenant-b"})), "tenant-a"),
        (_identity(), "tenant-b"),
    ),
)
def test_worker_access_boundary_denies_wrong_role_permission_or_tenant(
    identity, tenant_id
):
    provider, rehearsal = _rehearsal()

    with pytest.raises(SecretScopeError, match="authorized"):
        rehearsal.resolve("worker_transport", identity, tenant_id, now=NOW)

    assert provider.resolve_calls == []
    assert rehearsal.execution_authorized is False
    assert rehearsal.live_trading_authorized is False
