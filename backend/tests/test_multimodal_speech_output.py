from backend.multimodal.speech_output import SpeechOutput, SpeechOutputProvider, VoiceDescriptor


def test_tts_contract_is_provider_neutral_and_exposes_required_operations():
    assert {"synthesize","list_voices","supported_languages","streaming_supported"} <= set(SpeechOutputProvider.__dict__)
    voice=VoiceDescriptor("v-1","en","Synthetic",True)
    output=SpeechOutput("synthetic:1","SYNTHETIC_AUDIO_REFERENCE","LOCAL_TEST_ONLY","en",None)
    assert voice.synthetic_only and output.status == "SYNTHETIC_AUDIO_REFERENCE"
