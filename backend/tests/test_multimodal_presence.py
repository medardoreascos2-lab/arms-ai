import inspect
from backend.multimodal.presence import PresenceContext,PresenceState,RoomContext
def test_presence_defaults_unknown_without_location_inference():
 p=PresenceContext("t","u","s","d");assert p.state==PresenceState.UNKNOWN and p.room==RoomContext.ROOM_UNKNOWN
def test_presence_supports_only_device_assigned_approximate_room():
 p=PresenceContext("t","u","s","d",PresenceState.PRESENT,RoomContext.ROOM_ASSIGNED_BY_DEVICE,"device-config:room");assert p.room_assignment_reference
 source=inspect.getsource(PresenceContext).lower();assert "latitude" not in source and "longitude" not in source and "gps" not in source
