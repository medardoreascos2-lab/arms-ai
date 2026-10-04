"""Read-only distributed MEDAR presentation presence model."""
from dataclasses import dataclass
from enum import Enum
class PresenceDeviceKind(str,Enum):DESKTOP="DESKTOP";MOBILE="MOBILE";ROOM_DISPLAY="ROOM_DISPLAY";SMART_DISPLAY="SMART_DISPLAY";AR="AR";VR="VR";ROBOT="ROBOT"
@dataclass(frozen=True)
class DistributedPresence:
 tenant_id:str;user_id:str;session_id:str;device_id:str;screen_id:str|None;room_id:str|None;kind:PresenceDeviceKind;connected:bool;presentation_enabled:bool;device_control_authorized:bool=False
 def __post_init__(self):
  if self.device_control_authorized:raise ValueError("distributed presence cannot control devices")
class DistributedPresenceRegistry:
 def __init__(self):self._items:dict[tuple[str,str,str,str],DistributedPresence]={}
 def put(self,item):self._items[(item.tenant_id,item.user_id,item.session_id,item.device_id)]=item
 def for_user(self,tenant_id,user_id):return tuple(v for k,v in self._items.items() if k[0]==tenant_id and k[1]==user_id)
