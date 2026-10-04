import pytest
from backend.multimodal.session_isolation import IsolatedSessionStore,MultimodalScope,ScopedArtifact,SessionChannel
@pytest.mark.parametrize("channel",[SessionChannel.VOICE,SessionChannel.CAMERA,SessionChannel.NOTIFICATIONS,SessionChannel.AVATAR,SessionChannel.MEMORY_REFERENCES,SessionChannel.DAILY_INTELLIGENCE,SessionChannel.PRESENCE])
def test_multimodal_artifacts_never_cross_user_tenant_session_or_device(channel):
 store=IsolatedSessionStore();owner=MultimodalScope("tenant-a","user-a","session-a","device-a");item=ScopedArtifact("artifact",owner,channel,"reference:1");store.append(item);assert store.read(owner,channel)==(item,)
 for foreign in (MultimodalScope("tenant-a","user-b","session-a","device-a"),MultimodalScope("tenant-b","user-a","session-a","device-a"),MultimodalScope("tenant-a","user-a","session-b","device-a"),MultimodalScope("tenant-a","user-a","session-a","device-b")):assert store.read(foreign,channel)==()
