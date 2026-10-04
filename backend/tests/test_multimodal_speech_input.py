from typing import get_type_hints

from backend.multimodal.speech_input import SpeechInputProvider, SpeechTranscript


def test_speech_input_contract_is_provider_neutral_and_complete():
    assert {"transcribe", "detect_language", "streaming_supported", "supported_formats"} <= set(SpeechInputProvider.__dict__)
    transcript=SpeechTranscript(text="hello",language="en",confidence=0.9,provider="LOCAL_TEST_ONLY",synthetic=True)
    assert transcript.synthetic and transcript.text == "hello"
