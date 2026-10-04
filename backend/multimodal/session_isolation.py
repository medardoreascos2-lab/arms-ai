"""Tenant/user/session/device isolation for multimodal artifact references."""

from dataclasses import dataclass
from enum import Enum

class SessionChannel(str,Enum):
 VOICE="VOICE";CAMERA="CAMERA";NOTIFICATIONS="NOTIFICATIONS";AVATAR="AVATAR";MEMORY_REFERENCES="MEMORY_REFERENCES";DAILY_INTELLIGENCE="DAILY_INTELLIGENCE";PRESENCE="PRESENCE"
@dataclass(frozen=True)
class MultimodalScope:
 tenant_id:str;user_id:str;session_id:str;device_id:str
@dataclass(frozen=True)
class ScopedArtifact:
 artifact_id:str;scope:MultimodalScope;channel:SessionChannel;content_reference:str

class IsolatedSessionStore:
 def __init__(self):self._items:dict[tuple[MultimodalScope,SessionChannel],list[ScopedArtifact]]={}
 def append(self,item:ScopedArtifact):self._items.setdefault((item.scope,item.channel),[]).append(item)
 def read(self,scope:MultimodalScope,channel:SessionChannel)->tuple[ScopedArtifact,...]:return tuple(self._items.get((scope,channel),()))
