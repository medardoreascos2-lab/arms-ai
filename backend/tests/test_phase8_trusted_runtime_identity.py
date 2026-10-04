"""R108D local authenticated identity issuance and provenance tests."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.medar.memory_access import MemoryPurpose
from backend.medar.trusted_runtime_identity import (
    IdentityClassification, LocalAdminIdentityAuthority, LocalIdentityAssignment,
    RuntimeMemoryPermission,
)
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)


def _authority(clock=lambda: NOW):
    return LocalAdminIdentityAuthority(
        AdminAuthorizationV2(token="synthetic-test-token"),
        LocalIdentityAssignment(
            "owner-a", "tenant-a", "session-a", "medar-local",
            MemoryPurpose.TECHNICAL_ASSISTANCE,
            frozenset({RuntimeMemoryPermission.READ}),
        ),
        clock=clock,
    )


def test_identity_comes_from_authenticated_trusted_assignment():
    authority = _authority()
    with pytest.raises(PermissionError):
        authority.issue(None)
    with pytest.raises(PermissionError):
        authority.issue("wrong-synthetic-token")
    identity = authority.issue("synthetic-test-token")
    authority.require_valid(identity)
    assert (identity.owner_id, identity.tenant_id, identity.session_id, identity.service_id) == (
        "owner-a", "tenant-a", "session-a", "medar-local",
    )
    assert identity.classification is IdentityClassification.PRIVILEGED_LOCAL
    assert identity.authentication_source == "LOCAL_ADMIN_CREDENTIAL"
    assert identity.expires_at > identity.issued_at


def test_forged_changed_or_expired_identity_fails_validation():
    authority = _authority(clock=lambda: NOW)
    identity = authority.issue("synthetic-test-token")
    for changed in (
        replace(identity, owner_id="other"), replace(identity, tenant_id="other"),
        replace(identity, session_id="other"), replace(identity, service_id="other"),
    ):
        with pytest.raises(PermissionError):
            authority.require_valid(changed)
    with pytest.raises(PermissionError):
        _authority().require_valid(identity)
    with pytest.raises(PermissionError):
        replace(identity, classification=IdentityClassification.ANONYMOUS)
    current = [NOW]
    expiring = _authority(clock=lambda: current[0])
    expiring_identity = expiring.issue("synthetic-test-token")
    current[0] = NOW + timedelta(minutes=16)
    with pytest.raises(PermissionError):
        expiring.require_valid(expiring_identity)
