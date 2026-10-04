import pytest
from backend.multimodal.distributed_presence import DistributedPresence,DistributedPresenceRegistry,PresenceDeviceKind
def test_distributed_presence_models_future_surfaces_without_control():
 assert {x.value for x in PresenceDeviceKind}=={"DESKTOP","MOBILE","ROOM_DISPLAY","SMART_DISPLAY","AR","VR","ROBOT"}
 value=DistributedPresence("t","u","s","d","screen","room",PresenceDeviceKind.DESKTOP,True,True);store=DistributedPresenceRegistry();store.put(value);assert store.for_user("t","u")== (value,) and not value.device_control_authorized
def test_distributed_presence_rejects_device_control_authority():
 with pytest.raises(ValueError):DistributedPresence("t","u","s","d",None,None,PresenceDeviceKind.ROBOT,True,True,True)
