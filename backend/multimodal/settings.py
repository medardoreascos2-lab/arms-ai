"""Conservative user-scoped multimodal settings defaults."""
from dataclasses import dataclass
@dataclass(frozen=True)
class MultimodalSettings:
 tenant_id:str;user_id:str;voice_enabled:bool=False;camera_enabled:bool=False;avatar_enabled:bool=False;presence_enabled:bool=False;external_notifications_enabled:bool=False;quiet_hours_start:int=2200;quiet_hours_end:int=700;audio_retention:str="NO_STORAGE";image_retention:str="NO_STORAGE";camera_retention:str="NO_STORAGE";private_mode:bool=True
 def __post_init__(self):
  if self.external_notifications_enabled:raise ValueError("external notification delivery unavailable")
  if any(value not in {"NO_STORAGE","SESSION_ONLY"} for value in (self.audio_retention,self.image_retention,self.camera_retention)):raise ValueError("only conservative retention is available")
