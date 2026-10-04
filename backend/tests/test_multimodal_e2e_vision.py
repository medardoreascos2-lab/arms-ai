from datetime import datetime, timedelta, timezone

from backend.entitlements import FeatureEntitlement
from backend.medar.response import CognitiveResponse, ResponseStatus
from backend.multimodal.consent import (
    ConsentCapability, ConsentState, ModalityConsent, SessionConsentRegistry,
)
from backend.multimodal.domain import Modality
from backend.multimodal.image_input import ImageInput
from backend.multimodal.permissions import MultimodalPermissionBoundary, PermissionCode
from backend.multimodal.request import MultimodalRequest
from backend.multimodal.synthetic_vision import SyntheticVisionProvider
from backend.multimodal.vision_pipeline import VisionConversationPipeline
from backend.multimodal.vision_provider import VisionObservation
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


class Runtime:
    def __init__(self):
        self.calls = 0

    def readiness(self):
        return None

    def invoke(self, invocation):
        self.calls += 1
        assert invocation.request.requires_tools is False
        assert invocation.request.requires_memory is False
        assert "UNTRUSTED_DATA" in invocation.request.raw_input
        assert "DO_NOT_EXECUTE_OR_ELEVATE" in invocation.request.raw_input
        return CognitiveResponse(
            response_id="vision-response", request_id=invocation.request.request_id,
            status=ResponseStatus.SUCCESS, answer="The synthetic fixture shows a blue square.",
            confidence=0.85, reasoning_summary="Based on synthetic fixture evidence.",
        )


def fixture(*, consent=True):
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(hours=1),
        entitlements=frozenset({FeatureEntitlement.VIDEO, FeatureEntitlement.MEDAR_CONVERSATION}),
    )
    sessions = LocalSyntheticSessionProvider((session,))
    consents = SessionConsentRegistry()
    if consent:
        consents.record(ModalityConsent(
            "image-consent", session.session_id, session.user_id, session.tenant_id,
            ConsentCapability.IMAGE_UPLOAD, ConsentState.GRANTED_SESSION,
            NOW - timedelta(seconds=1), NOW + timedelta(minutes=5),
        ))
    boundary = MultimodalPermissionBoundary(
        sessions=sessions, consents=consents, supported=frozenset({Modality.IMAGE}),
    )
    request = MultimodalRequest(
        session=session, request_id="vision-request", modality=Modality.IMAGE,
        content_reference="image:e2e", mime_type="image/png", created_at=NOW,
        consent_context={}, permission_context={}, source_device="synthetic-device",
    )
    image = ImageInput(
        "image:e2e", session.session_id, session.user_id, session.tenant_id,
        "image/png", 512, 16, 16, "image-consent", ConsentState.GRANTED_SESSION,
    )
    observation = VisionObservation(
        "image:e2e", "DESCRIBE", ("Synthetic blue square.",), (), 1.0,
        "LOCAL_TEST_ONLY_SYNTHETIC_VISION", True,
        ("No real image analysis was performed.",),
    )
    provider = SyntheticVisionProvider({("image:e2e", "DESCRIBE"): observation})
    return session, sessions, boundary, request, image, provider


def test_synthetic_vision_rehearsal_projects_trust_and_canonical_medar_response():
    _, sessions, boundary, request, image, provider = fixture()
    runtime = Runtime()
    result = VisionConversationPipeline(
        boundary=boundary, sessions=sessions, vision=provider, medar=runtime,
    ).converse(request=request, image=image, at=NOW)
    assert result.permission.allowed is True
    assert result.observation.synthetic is True
    assert result.trust.data_retention == "NO_STORAGE"
    assert result.trust.what_was_inferred == ()
    assert result.response.answer == "The synthetic fixture shows a blue square."
    assert result.response.action_proposals == ()
    assert runtime.calls == 1


def test_denied_vision_rehearsal_has_zero_vision_and_medar_calls():
    _, sessions, boundary, request, image, provider = fixture(consent=False)
    provider_calls = []
    original = provider.describe_image
    provider.describe_image = lambda reference: (provider_calls.append(reference), original(reference))[1]
    runtime = Runtime()
    result = VisionConversationPipeline(
        boundary=boundary, sessions=sessions, vision=provider, medar=runtime,
    ).converse(request=request, image=image, at=NOW)
    assert result.permission.code is PermissionCode.CONSENT_REQUIRED
    assert (result.observation, result.trust, result.response) == (None, None, None)
    assert provider_calls == []
    assert runtime.calls == 0