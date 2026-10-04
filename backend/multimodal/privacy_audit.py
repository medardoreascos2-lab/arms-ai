"""Content-free multimodal consent and capture audit events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from .consent import ConsentCapability


class PrivacyAuditEventName(str, Enum):
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_DENIED = "CONSENT_DENIED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    CAMERA_STARTED = "CAMERA_STARTED"
    CAMERA_STOPPED = "CAMERA_STOPPED"
    MIC_STARTED = "MIC_STARTED"
    MIC_STOPPED = "MIC_STOPPED"
    MEDIA_DELETED_REQUESTED = "MEDIA_DELETED_REQUESTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


@dataclass(frozen=True)
class PrivacyAuditEvent:
    event_id: str
    name: PrivacyAuditEventName
    session_id: str
    pseudonymous_subject_id: str
    capability: ConsentCapability | None
    occurred_at: datetime
    reason_code: str | None = None
    content_included: bool = False

    def __post_init__(self) -> None:
        if not self.event_id or not self.session_id or not self.pseudonymous_subject_id:
            raise ValueError("content-free audit scope required")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be UTC")
        if self.content_included:
            raise ValueError("privacy audit cannot include raw media or content")


class InMemoryPrivacyAudit:
    def __init__(self) -> None:
        self._events: list[PrivacyAuditEvent] = []

    def append(self, event: PrivacyAuditEvent) -> None:
        if not isinstance(event, PrivacyAuditEvent):
            raise ValueError("canonical privacy audit event required")
        self._events.append(event)

    def for_session(self, session_id: str) -> tuple[PrivacyAuditEvent, ...]:
        return tuple(event for event in self._events if event.session_id == session_id)
