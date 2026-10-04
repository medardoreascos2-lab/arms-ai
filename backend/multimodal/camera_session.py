"""Session-scoped camera state domain; default state is OFF."""

from dataclasses import dataclass,replace
from datetime import datetime
from enum import Enum


class CameraSessionState(str,Enum):
    OFF="OFF";PERMISSION_REQUIRED="PERMISSION_REQUIRED";ACTIVE="ACTIVE";PAUSED="PAUSED";STOPPED="STOPPED";REVOKED="REVOKED";ERROR="ERROR"

_ALLOWED={
 CameraSessionState.OFF:{CameraSessionState.PERMISSION_REQUIRED},
 CameraSessionState.PERMISSION_REQUIRED:{CameraSessionState.ACTIVE,CameraSessionState.REVOKED,CameraSessionState.ERROR},
 CameraSessionState.ACTIVE:{CameraSessionState.PAUSED,CameraSessionState.STOPPED,CameraSessionState.REVOKED,CameraSessionState.ERROR},
 CameraSessionState.PAUSED:{CameraSessionState.ACTIVE,CameraSessionState.STOPPED,CameraSessionState.REVOKED},
 CameraSessionState.STOPPED:set(),CameraSessionState.REVOKED:set(),CameraSessionState.ERROR:{CameraSessionState.STOPPED},
}

@dataclass(frozen=True)
class CameraSession:
 camera_session_id:str;session_id:str;user_id:str;tenant_id:str;device_id:str;state:CameraSessionState=CameraSessionState.OFF;consent_reference:str|None=None;updated_at:datetime|None=None
 def transition(self,state:CameraSessionState,at:datetime,consent_reference:str|None=None):
  if state not in _ALLOWED[self.state]: raise ValueError(f"invalid camera transition {self.state.value}->{state.value}")
  if state==CameraSessionState.ACTIVE and not (consent_reference or self.consent_reference): raise PermissionError("active camera requires consent reference")
  return replace(self,state=state,updated_at=at,consent_reference=consent_reference or self.consent_reference)
