"""Synthetic multiroom audio routing model; no speaker control."""
from dataclasses import dataclass
from enum import Enum
class VolumePolicy(str,Enum):MUTED="MUTED";QUIET="QUIET";NORMAL="NORMAL"
@dataclass(frozen=True)
class AudioZone:
 room_id:str;speaker_group:str;user_id:str;quiet_state:str;enabled:bool;volume_policy:VolumePolicy
@dataclass(frozen=True)
class AudioRoutePlan:
 audio_reference:str;room_id:str;speaker_group:str;status:str="SIMULATED_ROUTE_ONLY";device_control_authorized:bool=False

def simulate_route(audio_reference:str,zone:AudioZone)->AudioRoutePlan:
 if not zone.enabled or zone.volume_policy==VolumePolicy.MUTED:raise PermissionError("audio zone disabled or muted")
 return AudioRoutePlan(audio_reference,zone.room_id,zone.speaker_group)
