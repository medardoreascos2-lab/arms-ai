"""P107C read-only Product Security Center tests."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.product.security_center import (
    LocalSessionProjection,
    ProductSecurityProjection,
    SecurityEventProjection,
    SecurityEventSeverity,
    SecurityProjectionStatus,
    SensitivePermissionProjection,
)


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def projection(**overrides):
    body = {
        "tenant_id": "synthetic-tenant-1",
        "user_id": "synthetic-user-1",
        "local_sessions": (
            LocalSessionProjection(
                session_reference="synthetic-session-1",
                device_label="Synthetic local device",
                issued_at=NOW,
                expires_at=NOW + timedelta(hours=1),
                is_current=True,
                status="ACTIVE",
            ),
        ),
        "recent_events": (
            SecurityEventProjection(
                event_reference="synthetic-security-event-1",
                event_type="SESSION_STARTED",
                occurred_at=NOW,
                summary="Synthetic local session started.",
                severity=SecurityEventSeverity.INFORMATION,
            ),
        ),
        "mfa_status": SecurityProjectionStatus.INTEGRATION_PENDING,
        "passkey_status": SecurityProjectionStatus.INTEGRATION_PENDING,
        "sensitive_permissions": (
            SensitivePermissionProjection(
                permission="FINANCIAL_MUTATION",
                status="DENIED",
            ),
        ),
    }
    body.update(overrides)
    return ProductSecurityProjection(**body)


def test_security_projection_contains_required_read_only_surfaces():
    value = projection()
    assert value.local_sessions[0].is_current is True
    assert value.recent_events[0].event_type == "SESSION_STARTED"
    assert value.mfa_status is SecurityProjectionStatus.INTEGRATION_PENDING
    assert value.passkey_status is SecurityProjectionStatus.INTEGRATION_PENDING
    assert value.sensitive_permissions[0].status == "DENIED"
    assert value.auth_provider_provisioning_authorized is False
    assert value.credential_mutation_authorized is False


def test_security_projection_cannot_enable_auth_or_credential_mutation():
    with pytest.raises(ValidationError):
        projection(auth_provider_provisioning_authorized=True)
    with pytest.raises(ValidationError):
        projection(credential_mutation_authorized=True)


def test_security_projection_rejects_non_utc_events_and_sessions():
    with pytest.raises(ValidationError):
        LocalSessionProjection(
            session_reference="synthetic-session-1",
            device_label="Synthetic device",
            issued_at=datetime(2026, 10, 4, 12),
            expires_at=NOW,
            is_current=True,
            status="ACTIVE",
        )
    with pytest.raises(ValidationError):
        SecurityEventProjection(
            event_reference="synthetic-event-1",
            event_type="SESSION",
            occurred_at=datetime(2026, 10, 4, 12),
            summary="Invalid local time.",
            severity="WATCH",
        )
