"""Fail-closed permission boundary for every multimodal invocation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from backend.entitlements import FeatureEntitlement
from backend.product.customer_session import CustomerSessionProvider
from .consent import ConsentCapability, ConsentState, SessionConsentRegistry
from .domain import Modality
from .request import MultimodalRequest


class PermissionCode(str, Enum):
    ALLOWED = "ALLOWED"
    SESSION_INVALID = "SESSION_INVALID"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    ENTITLEMENT_REQUIRED = "ENTITLEMENT_REQUIRED"
    CONSENT_REQUIRED = "CONSENT_REQUIRED"
    MODALITY_UNSUPPORTED = "MODALITY_UNSUPPORTED"


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    code: PermissionCode


_ENTITLEMENT = {
    Modality.TEXT: FeatureEntitlement.MEDAR_CONVERSATION,
    Modality.AUDIO_INPUT: FeatureEntitlement.VOICE,
    Modality.AUDIO_OUTPUT: FeatureEntitlement.VOICE,
    Modality.IMAGE: FeatureEntitlement.VIDEO,
    Modality.DOCUMENT: FeatureEntitlement.VIDEO,
    Modality.CAMERA_FRAME: FeatureEntitlement.VIDEO,
    Modality.VIDEO_CLIP: FeatureEntitlement.VIDEO,
    Modality.AVATAR_OUTPUT: FeatureEntitlement.VIDEO,
    Modality.NOTIFICATION: FeatureEntitlement.NOTIFICATIONS,
}
_CONSENT = {
    Modality.AUDIO_INPUT: ConsentCapability.MICROPHONE,
    Modality.IMAGE: ConsentCapability.IMAGE_UPLOAD,
    Modality.DOCUMENT: ConsentCapability.IMAGE_UPLOAD,
    Modality.CAMERA_FRAME: ConsentCapability.CAMERA,
    Modality.VIDEO_CLIP: ConsentCapability.CAMERA,
}


class MultimodalPermissionBoundary:
    def __init__(self, *, sessions: CustomerSessionProvider,
                 consents: SessionConsentRegistry,
                 supported: frozenset[Modality]) -> None:
        self._sessions = sessions
        self._consents = consents
        self._supported = supported

    def authorize(self, request: MultimodalRequest, at: datetime) -> PermissionDecision:
        session = self._sessions.validate_session(request.session_id, at)
        if session is None:
            return PermissionDecision(False, PermissionCode.SESSION_INVALID)
        if session.user_id != request.user_id or session.tenant_id != request.tenant_id:
            return PermissionDecision(False, PermissionCode.SCOPE_MISMATCH)
        if request.modality not in self._supported:
            return PermissionDecision(False, PermissionCode.MODALITY_UNSUPPORTED)
        entitlements = self._sessions.resolve_entitlements(session, at)
        if _ENTITLEMENT[request.modality] not in entitlements:
            return PermissionDecision(False, PermissionCode.ENTITLEMENT_REQUIRED)
        capability = _CONSENT.get(request.modality)
        if capability is not None and self._consents.state(
            session_id=session.session_id, user_id=session.user_id,
            tenant_id=session.tenant_id, capability=capability, at=at,
        ) != ConsentState.GRANTED_SESSION:
            return PermissionDecision(False, PermissionCode.CONSENT_REQUIRED)
        return PermissionDecision(True, PermissionCode.ALLOWED)

    def execute(self, request: MultimodalRequest, at: datetime, *,
                capture: Callable[[MultimodalRequest], Any],
                invoke: Callable[[Any], Any],
                store: Callable[[Any], None]) -> tuple[PermissionDecision, Any | None]:
        decision = self.authorize(request, at)
        if not decision.allowed:
            return decision, None
        captured = capture(request)
        result = invoke(captured)
        store(result)
        return decision, result
