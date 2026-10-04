"""Explicit camera capture policy with visible active state."""

from datetime import datetime
from typing import Callable,Any
from .camera_session import CameraSession,CameraSessionState
from .consent import ConsentState

class CameraCaptureController:
 def __init__(self,session:CameraSession): self.session=session;self.visible_indicator=False
 def request_start(self,*,explicit_user_action:bool,at:datetime):
  if not explicit_user_action: raise PermissionError("explicit user action required")
  self.session=self.session.transition(CameraSessionState.PERMISSION_REQUIRED,at);return self.session
 def activate(self,*,consent_state:ConsentState,consent_reference:str,at:datetime):
  if consent_state!=ConsentState.GRANTED_SESSION: raise PermissionError("camera session consent required")
  self.session=self.session.transition(CameraSessionState.ACTIVE,at,consent_reference);self.visible_indicator=True;return self.session
 def capture(self,callback:Callable[[],Any])->Any:
  if self.session.state!=CameraSessionState.ACTIVE or not self.visible_indicator: raise PermissionError("camera capture is not active and visible")
  return callback()
 def pause(self,at:datetime): self.session=self.session.transition(CameraSessionState.PAUSED,at);self.visible_indicator=False
 def stop(self,at:datetime): self.session=self.session.transition(CameraSessionState.STOPPED,at);self.visible_indicator=False
 def revoke(self,at:datetime): self.session=self.session.transition(CameraSessionState.REVOKED,at);self.visible_indicator=False
