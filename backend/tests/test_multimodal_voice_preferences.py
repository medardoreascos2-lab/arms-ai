import pytest

from backend.multimodal.voice_preferences import VoicePreferences, VoicePreferenceStore


def test_voice_preferences_are_scoped_private_and_auto_speak_off_by_default():
    store=VoicePreferenceStore(); value=VoicePreferences(tenant_id="t",user_id="u",voice_id="synthetic-neutral",language="en");store.save(value)
    assert store.get("t","u") == value
    assert store.get("t","other") is None
    assert value.private_mode and not value.auto_speak and not value.biometric_cloning_allowed


def test_biometric_voice_cloning_is_structurally_rejected():
    with pytest.raises(ValueError): VoicePreferences(tenant_id="t",user_id="u",voice_id="clone",language="en",biometric_cloning_allowed=True)
