"""Customer session authority is immutable, UTC-only, and synthetic."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone

import pytest

from backend.entitlements import FeatureEntitlement, UserRole
from backend.product.customer_session import (
    CustomerSessionStatus,
    LocalSyntheticSessionProvider,
    TrustedCustomerSession,
    synthetic_customer_session,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def session(**overrides):
    base = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=15),
    )
    return replace(base, **overrides)


def test_session_requires_utc_ordered_times_and_immutable_scope():
    with pytest.raises(ValueError, match="UTC"):
        session(issued_at=datetime(2026, 10, 4, 11))
    with pytest.raises(ValueError, match="expiry"):
        session(expires_at=NOW - timedelta(minutes=1))
    source = session()
    with pytest.raises(FrozenInstanceError):
        source.user_id = "synthetic-user-2"
    with pytest.raises(TypeError):
        source.device_metadata["kind"] = "modified"
    assert source.session_metadata["environment"] == "LOCAL_TEST_ONLY"


def test_provider_accepts_only_synthetic_local_fixtures():
    with pytest.raises(ValueError, match="synthetic"):
        LocalSyntheticSessionProvider((session(user_id="real-user"),))
    with pytest.raises(ValueError, match="duplicate"):
        LocalSyntheticSessionProvider((session(), session()))
    with pytest.raises(ValueError, match="LOCAL_TEST_ONLY"):
        LocalSyntheticSessionProvider((session(auth_source="PRODUCTION"),))
    with pytest.raises(ValueError, match="LOCAL_TEST_ONLY"):
        LocalSyntheticSessionProvider((session(authentication_method="PASSWORD"),))


def test_provider_validates_expiry_revocation_and_unknown_identifier():
    provider = LocalSyntheticSessionProvider((session(),))
    assert provider.validate_session("synthetic-session-1", NOW) is not None
    assert provider.validate_session("unknown", NOW) is None
    assert provider.validate_session("synthetic-session-1", NOW + timedelta(minutes=15)) is None
    provider.revoke("synthetic-session-1")
    assert provider.validate_session("synthetic-session-1", NOW) is None


def test_provider_rejects_tampering_and_cross_provider_reuse():
    source = session()
    provider = LocalSyntheticSessionProvider((source,))
    second = LocalSyntheticSessionProvider((replace(source, user_id="synthetic-user-2"),))
    assert provider.resolve_identity(source, NOW).user_id == source.user_id
    assert provider.resolve_tenant(source, NOW) == source.tenant_id
    assert provider.resolve_roles(source, NOW) == frozenset({UserRole.VIEWER})
    assert provider.resolve_entitlements(source, NOW) == frozenset({
        FeatureEntitlement.MEDAR_CONVERSATION
    })
    for invalid in (replace(source, user_id="synthetic-user-2"),
                    replace(source, tenant_id="synthetic-tenant-2"),
                    replace(source, entitlements=frozenset())):
        with pytest.raises(PermissionError):
            provider.resolve_identity(invalid, NOW)
    with pytest.raises(PermissionError):
        second.resolve_identity(source, NOW)


def test_nonactive_session_statuses_fail_validation():
    for status in (CustomerSessionStatus.EXPIRED, CustomerSessionStatus.REVOKED,
                   CustomerSessionStatus.INVALID):
        provider = LocalSyntheticSessionProvider((session(status=status),))
        assert provider.validate_session("synthetic-session-1", NOW) is None
