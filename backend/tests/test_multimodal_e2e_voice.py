from datetime import datetime, timedelta, timezone

from backend.entitlements import FeatureEntitlement
from backend.medar.response import CognitiveResponse, ResponseStatus
from backend.multimodal.audio_validation import AudioInputDescriptor
from backend.multimodal.consent import (
    ConsentCapability,
    ConsentState,
    ModalityConsent,
    SessionConsentRegistry,
)
from backend.multimodal.domain import Modality
from backend.multimodal.permissions import MultimodalPermissionBoundary, PermissionCode
from backend.multimodal.request import MultimodalRequest
from backend.multimodal.synthetic_stt import SyntheticSpeechInputProvider
from backend.multimodal.synthetic_tts import SyntheticSpeechOutputProvider
from backend.multimodal.voice_pipeline import VoiceConversationPipeline
from backend.multimodal.voice_preferences import VoicePreferences
from backend.product.customer_session import LocalSyntheticSessionProvider, synthetic_customer_session

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


class RecordingStt(SyntheticSpeechInputProvider):
    def __init__(self, events):
        super().__init__({"audio:e2e": ("Summarize my day", "en")})
        self.events = events

    def transcribe(self, content_reference, mime_type):
        self.events.append("STT")
        return super().transcribe(content_reference, mime_type)


class RecordingMedar:
    def __init__(self, events):
        self.events = events

    def readiness(self):
        return None

    def invoke(self, invocation):
        self.events.append("MEDAR")
        assert invocation.request.requires_tools is False
        assert invocation.request.requires_memory is False
        return CognitiveResponse(
            response_id="response-e2e",
            request_id=invocation.request.request_id,
            status=ResponseStatus.SUCCESS,
            answer="Synthetic daily summary.",
            confidence=0.9,
            reasoning_summary="Synthetic fixture evidence.",
        )


class RecordingTts(SyntheticSpeechOutputProvider):
    def __init__(self, events):
        self.events = events

    def synthesize(self, text, voice_id, language, speaking_rate):
        self.events.append("TTS")
        return super().synthesize(text, voice_id, language, speaking_rate)


def fixture(*, consent=True):
    session = synthetic_customer_session(
        issued_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1),
        entitlements=frozenset({FeatureEntitlement.VOICE, FeatureEntitlement.MEDAR_CONVERSATION}),
    )
    sessions = LocalSyntheticSessionProvider((session,))
    consents = SessionConsentRegistry()
    if consent:
        consents.record(ModalityConsent(
            "consent-e2e", session.session_id, session.user_id, session.tenant_id,
            ConsentCapability.MICROPHONE, ConsentState.GRANTED_SESSION,
            NOW - timedelta(seconds=1), NOW + timedelta(minutes=5),
        ))
    boundary = MultimodalPermissionBoundary(
        sessions=sessions, consents=consents, supported=frozenset({Modality.AUDIO_INPUT}),
    )
    request = MultimodalRequest(
        session=session, request_id="request-e2e", modality=Modality.AUDIO_INPUT,
        content_reference="audio:e2e", mime_type="audio/wav", created_at=NOW,
        consent_context={}, permission_context={}, source_device="synthetic-device",
    )
    audio = AudioInputDescriptor(
        "audio:e2e", session.session_id, session.user_id, session.tenant_id,
        "audio/wav", "wav", 128, 1.0,
    )
    return session, sessions, boundary, request, audio


def test_synthetic_voice_rehearsal_runs_session_consent_audio_stt_medar_tts_response():
    session, sessions, boundary, request, audio = fixture()
    events = []
    pipeline = VoiceConversationPipeline(
        boundary=boundary, sessions=sessions, stt=RecordingStt(events),
        medar=RecordingMedar(events), tts=RecordingTts(events),
    )
    result = pipeline.converse(
        request=request, audio=audio,
        preferences=VoicePreferences(session.tenant_id, session.user_id, "synthetic-neutral", "en"),
        at=NOW,
    )
    assert events == ["STT", "MEDAR", "TTS"]
    assert result.permission.allowed is True
    assert result.transcript.text == "Summarize my day"
    assert result.response.answer == "Synthetic daily summary."
    assert result.audio.status == "SYNTHETIC_AUDIO_REFERENCE"
    assert result.response.action_proposals == ()
    assert result.response.tool_evidence == ()


def test_denied_voice_rehearsal_has_zero_provider_or_execution_side_effects():
    session, sessions, boundary, request, audio = fixture(consent=False)
    events = []
    pipeline = VoiceConversationPipeline(
        boundary=boundary, sessions=sessions, stt=RecordingStt(events),
        medar=RecordingMedar(events), tts=RecordingTts(events),
    )
    result = pipeline.converse(
        request=request, audio=audio,
        preferences=VoicePreferences(session.tenant_id, session.user_id, "synthetic-neutral", "en"),
        at=NOW,
    )
    assert result.permission.code is PermissionCode.CONSENT_REQUIRED
    assert (result.transcript, result.response, result.audio) == (None, None, None)
    assert events == []