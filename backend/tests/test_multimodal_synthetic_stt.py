import pytest

from backend.multimodal.synthetic_stt import SyntheticSpeechInputProvider


def test_synthetic_stt_is_deterministic_and_explicitly_not_streaming():
    provider=SyntheticSpeechInputProvider({"audio:1":("hello MEDAR","en")})
    assert provider.transcribe("audio:1","audio/wav") == provider.transcribe("audio:1","audio/wav")
    assert provider.transcribe("audio:1","audio/wav").synthetic
    assert not provider.streaming_supported()


def test_synthetic_stt_never_invents_missing_transcript():
    provider=SyntheticSpeechInputProvider({})
    with pytest.raises(LookupError): provider.transcribe("missing","audio/wav")
