"""Deterministic presentation-only avatar state machine."""
from dataclasses import dataclass,replace
from enum import Enum
class AvatarState(str,Enum):OFFLINE="OFFLINE";IDLE="IDLE";LISTENING="LISTENING";THINKING="THINKING";SPEAKING="SPEAKING";NOTIFYING="NOTIFYING";ERROR="ERROR"
_ALLOWED={AvatarState.OFFLINE:{AvatarState.IDLE},AvatarState.IDLE:{AvatarState.LISTENING,AvatarState.THINKING,AvatarState.SPEAKING,AvatarState.NOTIFYING,AvatarState.OFFLINE},AvatarState.LISTENING:{AvatarState.THINKING,AvatarState.IDLE,AvatarState.ERROR},AvatarState.THINKING:{AvatarState.SPEAKING,AvatarState.IDLE,AvatarState.ERROR},AvatarState.SPEAKING:{AvatarState.IDLE,AvatarState.ERROR},AvatarState.NOTIFYING:{AvatarState.IDLE,AvatarState.ERROR},AvatarState.ERROR:{AvatarState.IDLE,AvatarState.OFFLINE}}
@dataclass(frozen=True)
class AvatarStateMachine:
 state:AvatarState=AvatarState.OFFLINE
 def transition(self,target:AvatarState):
  if target not in _ALLOWED[self.state]:raise ValueError(f"invalid avatar transition {self.state}->{target}")
  return replace(self,state=target)
