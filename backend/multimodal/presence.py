"""Presence is coarse, explicit, and never a precise inferred location."""

from dataclasses import dataclass
from enum import Enum

class PresenceState(str,Enum):PRESENT="PRESENT";AWAY="AWAY";UNKNOWN="UNKNOWN"
class RoomContext(str,Enum):ROOM_UNKNOWN="ROOM_UNKNOWN";ROOM_ASSIGNED_BY_DEVICE="ROOM_ASSIGNED_BY_DEVICE"

@dataclass(frozen=True)
class PresenceContext:
 tenant_id:str;user_id:str;session_id:str;device_id:str;state:PresenceState=PresenceState.UNKNOWN;room:RoomContext=RoomContext.ROOM_UNKNOWN;room_assignment_reference:str|None=None
 def __post_init__(self):
  if self.room==RoomContext.ROOM_ASSIGNED_BY_DEVICE and not self.room_assignment_reference:raise ValueError("device room assignment reference required")
