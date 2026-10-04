"""Metadata-only camera frame contract with no long-term storage default."""

from dataclasses import dataclass
from datetime import datetime,timedelta
from enum import Enum

class FrameRetentionPolicy(str,Enum):
 NO_STORAGE="NO_STORAGE";SESSION_ONLY="SESSION_ONLY"

@dataclass(frozen=True)
class CameraFrame:
 frame_id:str;camera_session_id:str;timestamp:datetime;mime:str;width:int;height:int;retention_policy:FrameRetentionPolicy;consent_reference:str;content_reference:str
 def __post_init__(self):
  if self.timestamp.tzinfo is None or self.timestamp.utcoffset()!=timedelta(0):raise ValueError("timestamp must be UTC")
  if self.mime not in {"image/jpeg","image/png","image/webp"}:raise ValueError("unsupported frame mime")
  if self.width<=0 or self.height<=0:raise ValueError("positive frame dimensions required")
  if not self.consent_reference or not self.camera_session_id:raise PermissionError("camera session consent required")
