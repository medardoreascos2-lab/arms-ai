"""Explicit, session-scoped consent for sensitive multimodal capabilities."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum


class ConsentState(str, Enum):
    NOT_REQUESTED = "NOT_REQUESTED"
    GRANTED_SESSION = "GRANTED_SESSION"
    DENIED = "DENIED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ConsentCapability(str, Enum):
    MICROPHONE = "MICROPHONE"
    CAMERA = "CAMERA"
    IMAGE_UPLOAD = "IMAGE_UPLOAD"
    AUDIO_STORAGE = "AUDIO_STORAGE"
    CAMERA_STORAGE = "CAMERA_STORAGE"
    VOICE_PROFILE = "VOICE_PROFILE"
    PRESENCE = "PRESENCE"
    WEARABLE_DATA = "WEARABLE_DATA"
    HOME_AUTOMATION = "HOME_AUTOMATION"


@dataclass(frozen=True)
class ModalityConsent:
    consent_id: str
    session_id: str
    user_id: str
    tenant_id: str
    capability: ConsentCapability
    state: ConsentState
    decided_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if any(not value for value in (self.consent_id, self.session_id, self.user_id, self.tenant_id)):
            raise ValueError("scoped consent identifiers required")
        for name in ("decided_at", "expires_at"):
            value = getattr(self, name)
            if value.tzinfo is None or value.utcoffset() != timedelta(0):
                raise ValueError(f"{name} must be UTC")
        if self.expires_at <= self.decided_at:
            raise ValueError("consent expiry must follow decision")

    def effective_state(self, at: datetime) -> ConsentState:
        if self.state == ConsentState.GRANTED_SESSION and at >= self.expires_at:
            return ConsentState.EXPIRED
        return self.state


class SessionConsentRegistry:
    def __init__(self) -> None:
        self._records: dict[tuple[str, ConsentCapability], ModalityConsent] = {}

    def record(self, consent: ModalityConsent) -> None:
        self._records[(consent.session_id, consent.capability)] = consent

    def state(self, *, session_id: str, user_id: str, tenant_id: str,
              capability: ConsentCapability, at: datetime) -> ConsentState:
        record = self._records.get((session_id, capability))
        if record is None:
            return ConsentState.NOT_REQUESTED
        if record.user_id != user_id or record.tenant_id != tenant_id:
            return ConsentState.DENIED
        return record.effective_state(at)

    def revoke(self, session_id: str, capability: ConsentCapability, at: datetime) -> None:
        record = self._records.get((session_id, capability))
        if record is not None:
            self._records[(session_id, capability)] = replace(
                record, state=ConsentState.REVOKED, decided_at=at
            )
