import pytest
from backend.multimodal.multiroom_audio import AudioZone,VolumePolicy,simulate_route
def test_multiroom_route_is_simulation_only_with_zero_device_control():
 plan=simulate_route("synthetic-audio:1",AudioZone("room","group","user","NORMAL",True,VolumePolicy.NORMAL));assert plan.status=="SIMULATED_ROUTE_ONLY" and not plan.device_control_authorized
def test_disabled_or_muted_zone_cannot_route():
 with pytest.raises(PermissionError):simulate_route("audio",AudioZone("room","group","user","QUIET",True,VolumePolicy.MUTED))
