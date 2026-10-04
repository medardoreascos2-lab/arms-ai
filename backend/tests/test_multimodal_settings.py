import pytest
from backend.multimodal.settings import MultimodalSettings
def test_multimodal_settings_default_every_sensitive_modality_off_and_private():
 s=MultimodalSettings("t","u");assert not any((s.voice_enabled,s.camera_enabled,s.avatar_enabled,s.presence_enabled,s.external_notifications_enabled));assert s.private_mode and s.camera_retention=="NO_STORAGE"
def test_external_delivery_and_long_retention_are_rejected():
 with pytest.raises(ValueError):MultimodalSettings("t","u",external_notifications_enabled=True)
 with pytest.raises(ValueError):MultimodalSettings("t","u",camera_retention="FOREVER")
