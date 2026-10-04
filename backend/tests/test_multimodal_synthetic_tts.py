from backend.multimodal.synthetic_tts import SyntheticSpeechOutputProvider


def test_synthetic_tts_returns_only_deterministic_reference_metadata():
    provider=SyntheticSpeechOutputProvider(); a=provider.synthesize("Hello","synthetic-neutral","en",1.0); b=provider.synthesize("Hello","synthetic-neutral","en",1.0)
    assert a == b and a.status == "SYNTHETIC_AUDIO_REFERENCE"
    assert a.duration_seconds is None and not provider.streaming_supported()
