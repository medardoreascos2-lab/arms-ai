from datetime import datetime, timedelta, timezone

from backend.multimodal.consent import (
    ConsentCapability, ConsentState, ModalityConsent, SessionConsentRegistry,
)

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def grant(capability=ConsentCapability.MICROPHONE):
    return ModalityConsent(
        consent_id="consent-1", session_id="session-1", user_id="user-1",
        tenant_id="tenant-1", capability=capability,
        state=ConsentState.GRANTED_SESSION, decided_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
    )


def test_consent_is_separate_session_scoped_and_expires():
    registry = SessionConsentRegistry(); registry.record(grant())
    assert registry.state(session_id="session-1", user_id="user-1", tenant_id="tenant-1", capability=ConsentCapability.MICROPHONE, at=NOW) == ConsentState.GRANTED_SESSION
    assert registry.state(session_id="session-1", user_id="user-1", tenant_id="tenant-1", capability=ConsentCapability.CAMERA, at=NOW) == ConsentState.NOT_REQUESTED
    assert registry.state(session_id="session-1", user_id="user-1", tenant_id="tenant-1", capability=ConsentCapability.MICROPHONE, at=NOW + timedelta(hours=1)) == ConsentState.EXPIRED


def test_consent_scope_mismatch_denies_and_revoke_is_immediate():
    registry = SessionConsentRegistry(); registry.record(grant())
    assert registry.state(session_id="session-1", user_id="other", tenant_id="tenant-1", capability=ConsentCapability.MICROPHONE, at=NOW) == ConsentState.DENIED
    registry.revoke("session-1", ConsentCapability.MICROPHONE, NOW + timedelta(seconds=1))
    assert registry.state(session_id="session-1", user_id="user-1", tenant_id="tenant-1", capability=ConsentCapability.MICROPHONE, at=NOW + timedelta(seconds=2)) == ConsentState.REVOKED
