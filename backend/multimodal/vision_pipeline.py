"""Permissioned image -> vision -> canonical MEDAR -> trust projection pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json

from backend.api.schemas.product_medar import ProductMedarPrompt, ProductMedarResponse
from backend.product.customer_session import CustomerSessionProvider
from backend.product.medar_adapter import ProductMedarRuntime, make_invocation, project_cognitive_response
from .consent import ConsentState
from .domain import Modality
from .image_input import ImageInput, ImageLimits, validate_image_input
from .injection_defense import (
    ExtractedMediaSegment,
    ExtractedSegmentKind,
    build_untrusted_media_context,
)
from .permissions import MultimodalPermissionBoundary, PermissionDecision
from .request import MultimodalRequest
from .trust import EvidenceClass, MultimodalTrustProjection, TrustEvidence
from .vision_provider import VisionObservation, VisionProvider


@dataclass(frozen=True)
class VisionConversationResult:
    permission: PermissionDecision
    observation: VisionObservation | None = None
    trust: MultimodalTrustProjection | None = None
    response: ProductMedarResponse | None = None


class VisionConversationPipeline:
    def __init__(self, *, boundary: MultimodalPermissionBoundary,
                 sessions: CustomerSessionProvider, vision: VisionProvider,
                 medar: ProductMedarRuntime,
                 image_limits: ImageLimits = ImageLimits()) -> None:
        self._boundary = boundary
        self._sessions = sessions
        self._vision = vision
        self._medar = medar
        self._limits = image_limits

    def converse(self, *, request: MultimodalRequest, image: ImageInput,
                 at: datetime) -> VisionConversationResult:
        def process(_: ImageInput):
            validate_image_input(image, request, self._limits)
            observation = self._vision.describe_image(image.content_reference)
            segments = tuple(
                ExtractedMediaSegment(ExtractedSegmentKind.CONTENT, statement)
                for statement in observation.observations + observation.visible_text
            )
            context = build_untrusted_media_context(
                content_reference=image.content_reference,
                modality=Modality.IMAGE,
                segments=segments,
            )
            session = self._sessions.validate_session(request.session_id, at)
            if session is None:
                raise PermissionError("session expired before MEDAR invocation")
            prompt = ProductMedarPrompt(
                request_id=request.request_id,
                conversation_id=request.session_id,
                message=json.dumps(dict(context.as_model_context())),
                locale="en",
                response_profile="STANDARD",
            )
            invocation = make_invocation(
                prompt, session, self._sessions.resolve_entitlements(session, at)
            )
            response = project_cognitive_response(
                self._medar.invoke(invocation), request.request_id
            )
            trust = MultimodalTrustProjection(
                source=image.content_reference,
                modality=Modality.IMAGE,
                provider=observation.provider,
                confidence=observation.confidence,
                consent_state=ConsentState.GRANTED_SESSION,
                data_retention="NO_STORAGE",
                limitations=observation.limitations or ("PROVIDER_LIMITATIONS_UNSPECIFIED",),
                what_was_observed=observation.observations + observation.visible_text,
                what_was_inferred=(),
                evidence=(
                    TrustEvidence(EvidenceClass.SYNTHETIC, (observation.provider,)),
                    TrustEvidence(EvidenceClass.OBSERVATION, observation.observations + observation.visible_text),
                ),
            )
            return observation, trust, response

        decision, value = self._boundary.execute(
            request, at, capture=lambda _: image, invoke=process, store=lambda _: None
        )
        if not decision.allowed or value is None:
            return VisionConversationResult(permission=decision)
        observation, trust, response = value
        return VisionConversationResult(
            permission=decision, observation=observation, trust=trust, response=response
        )