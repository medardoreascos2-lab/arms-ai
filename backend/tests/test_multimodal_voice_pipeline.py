from datetime import datetime,timedelta,timezone

from backend.entitlements import FeatureEntitlement
from backend.medar.response import CognitiveResponse,ResponseStatus
from backend.multimodal.audio_validation import AudioInputDescriptor
from backend.multimodal.consent import ConsentCapability,ConsentState,ModalityConsent,SessionConsentRegistry
from backend.multimodal.domain import Modality
from backend.multimodal.permissions import MultimodalPermissionBoundary
from backend.multimodal.request import MultimodalRequest
from backend.multimodal.synthetic_stt import SyntheticSpeechInputProvider
from backend.multimodal.synthetic_tts import SyntheticSpeechOutputProvider
from backend.multimodal.voice_pipeline import VoiceConversationPipeline
from backend.multimodal.voice_preferences import VoicePreferences
from backend.product.customer_session import LocalSyntheticSessionProvider,synthetic_customer_session

NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)

class Runtime:
    def __init__(self): self.calls=0
    def readiness(self): return None
    def invoke(self,invocation):
        self.calls+=1
        assert not invocation.request.requires_tools and not invocation.request.requires_memory
        return CognitiveResponse(response_id="response-1",request_id=invocation.request.request_id,status=ResponseStatus.SUCCESS,answer="Canonical answer",confidence=.8,reasoning_summary="Evidence summary")


def test_voice_pipeline_uses_permission_stt_canonical_medar_and_tts_in_order():
    session=synthetic_customer_session(issued_at=NOW-timedelta(minutes=1),expires_at=NOW+timedelta(hours=1),entitlements=frozenset({FeatureEntitlement.VOICE,FeatureEntitlement.MEDAR_CONVERSATION}))
    sessions=LocalSyntheticSessionProvider((session,));consents=SessionConsentRegistry();consents.record(ModalityConsent("c",session.session_id,session.user_id,session.tenant_id,ConsentCapability.MICROPHONE,ConsentState.GRANTED_SESSION,NOW-timedelta(seconds=1),NOW+timedelta(minutes=5)))
    boundary=MultimodalPermissionBoundary(sessions=sessions,consents=consents,supported=frozenset({Modality.AUDIO_INPUT}))
    request=MultimodalRequest(session=session,request_id="request-1",modality=Modality.AUDIO_INPUT,content_reference="audio:1",mime_type="audio/wav",created_at=NOW,consent_context={},permission_context={},source_device="device")
    audio=AudioInputDescriptor("audio:1",session.session_id,session.user_id,session.tenant_id,"audio/wav","wav",100,1)
    runtime=Runtime();pipeline=VoiceConversationPipeline(boundary=boundary,sessions=sessions,stt=SyntheticSpeechInputProvider({"audio:1":("hello","en")}),medar=runtime,tts=SyntheticSpeechOutputProvider())
    result=pipeline.converse(request=request,audio=audio,preferences=VoicePreferences(session.tenant_id,session.user_id,"synthetic-neutral","en"),at=NOW)
    assert result.permission.allowed and result.transcript.text=="hello"
    assert result.response.answer=="Canonical answer"
    assert result.audio.status=="SYNTHETIC_AUDIO_REFERENCE" and runtime.calls==1
