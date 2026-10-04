from backend.multimodal.voice_degraded import VoiceDegradedState,voice_degraded


def test_all_voice_degraded_states_are_truthful_and_offer_text_explicitly():
    assert {x.value for x in VoiceDegradedState} == {"MIC_PERMISSION_DENIED","MIC_UNAVAILABLE","STT_UNAVAILABLE","TTS_UNAVAILABLE","AUDIO_INVALID","MODEL_UNAVAILABLE"}
    for state in VoiceDegradedState:
        result=voice_degraded(state)
        assert result.text_fallback_offered and result.audio_reference is None
        assert not result.provider_switched and result.message
