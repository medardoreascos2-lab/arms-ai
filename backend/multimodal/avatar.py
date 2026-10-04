"""Presentation-only avatar instructions with zero operational authority."""

from dataclasses import dataclass
from enum import Enum

class AvatarAction(str,Enum):SPEAK="speak";IDLE="idle";LISTEN="listen";ACKNOWLEDGE="acknowledge";GESTURE="gesture";POINT="point"
class AvatarEmotionStyle(str,Enum):NEUTRAL="NEUTRAL";WARM="WARM";CALM="CALM";FOCUSED="FOCUSED"
@dataclass(frozen=True)
class AvatarInstruction:
 instruction_id:str;action:AvatarAction;transcript_reference:str|None=None;audio_reference:str|None=None;gesture:str|None=None;attention_target:str|None=None;emotion_display:AvatarEmotionStyle=AvatarEmotionStyle.NEUTRAL;presentation_only:bool=True;user_emotion_inferred:bool=False;execution_authorized:bool=False
 def __post_init__(self):
  if not self.presentation_only or self.user_emotion_inferred or self.execution_authorized:raise ValueError("avatar instructions are presentation only")
  if self.action==AvatarAction.SPEAK and not self.transcript_reference:raise ValueError("speak requires transcript reference")
