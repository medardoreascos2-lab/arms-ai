from backend.multimodal.capability_registry import CapabilityState,MultimodalCapability,validated_local_registry
def test_registry_never_advertises_unverified_qwen_vision_or_media_capability():
 r=validated_local_registry();assert r.get("ollama-local",MultimodalCapability.TEXT_GENERATION).state==CapabilityState.AVAILABLE
 for cap in (MultimodalCapability.VISION,MultimodalCapability.STT,MultimodalCapability.TTS,MultimodalCapability.IMAGE_GENERATION,MultimodalCapability.VIDEO_GENERATION,MultimodalCapability.LIP_SYNC):assert r.get("ollama-local",cap).state==CapabilityState.UNAVAILABLE
def test_synthetic_capabilities_are_explicitly_local_test_only():
 r=validated_local_registry();assert r.get("synthetic-vision",MultimodalCapability.VISION).state==CapabilityState.LOCAL_TEST_ONLY
