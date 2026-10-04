"""Permissioned audio -> STT -> canonical MEDAR -> TTS pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from backend.api.schemas.product_medar import ProductMedarPrompt, ProductMedarResponse
from backend.product.customer_session import CustomerSessionProvider
from backend.product.medar_adapter import ProductMedarRuntime, make_invocation, project_cognitive_response
from .audio_validation import AudioInputDescriptor, AudioInputLimits, validate_audio_input
from .permissions import MultimodalPermissionBoundary, PermissionDecision
from .request import MultimodalRequest
from .speech_input import SpeechInputProvider, SpeechTranscript
from .speech_output import SpeechOutput, SpeechOutputProvider
from .voice_preferences import VoicePreferences


@dataclass(frozen=True)
class VoiceConversationResult:
    permission: PermissionDecision
    transcript: SpeechTranscript | None = None
    response: ProductMedarResponse | None = None
    audio: SpeechOutput | None = None


class VoiceConversationPipeline:
    def __init__(self, *, boundary: MultimodalPermissionBoundary,
                 sessions: CustomerSessionProvider, stt: SpeechInputProvider,
                 medar: ProductMedarRuntime, tts: SpeechOutputProvider,
                 audio_limits: AudioInputLimits = AudioInputLimits()) -> None:
        self._boundary=boundary; self._sessions=sessions; self._stt=stt
        self._medar=medar; self._tts=tts; self._limits=audio_limits

    def converse(self, *, request: MultimodalRequest, audio: AudioInputDescriptor,
                 preferences: VoicePreferences, at: datetime) -> VoiceConversationResult:
        def process(_: AudioInputDescriptor):
            validate_audio_input(audio,request,self._limits)
            transcript=self._stt.transcribe(audio.content_reference,audio.mime_type)
            session=self._sessions.validate_session(request.session_id,at)
            if session is None:
                raise PermissionError("session expired before MEDAR invocation")
            prompt=ProductMedarPrompt(request_id=request.request_id,conversation_id=request.session_id,message=transcript.text,locale=transcript.language,response_profile=preferences.verbosity.value)
            invocation=make_invocation(prompt,session,self._sessions.resolve_entitlements(session,at))
            cognitive=self._medar.invoke(invocation)
            projected=project_cognitive_response(cognitive,request.request_id)
            if projected.answer is None:
                raise RuntimeError("canonical MEDAR response unavailable")
            speech=self._tts.synthesize(projected.answer,preferences.voice_id,preferences.language,preferences.speaking_rate)
            return transcript,projected,speech
        decision,value=self._boundary.execute(request,at,capture=lambda _:audio,invoke=process,store=lambda _:None)
        if not decision.allowed or value is None:
            return VoiceConversationResult(permission=decision)
        transcript,response,speech=value
        return VoiceConversationResult(permission=decision,transcript=transcript,response=response,audio=speech)
