"""Provider-neutral avatar lip-sync timing seam."""
from dataclasses import dataclass
from typing import Protocol
@dataclass(frozen=True)
class MouthCue:
 start_ms:int;end_ms:int;viseme:str
 def __post_init__(self):
  if self.start_ms<0 or self.end_ms<=self.start_ms or not self.viseme:raise ValueError("valid mouth cue timing required")
@dataclass(frozen=True)
class LipSyncSequence:
 audio_reference:str;duration_ms:int;cues:tuple[MouthCue,...];provider:str;synthetic:bool
class LipSyncProvider(Protocol):
 def audio_timing(self,audio_reference:str)->int:...
 def viseme_timing(self,audio_reference:str)->tuple[MouthCue,...]:...
 def mouth_cue_sequence(self,audio_reference:str)->LipSyncSequence:...
class SyntheticLipSyncProvider:
 provider_id="LOCAL_TEST_ONLY_SYNTHETIC_LIP_SYNC"
 def __init__(self,fixtures:dict[str,LipSyncSequence]):self._fixtures=dict(fixtures)
 def mouth_cue_sequence(self,audio_reference):
  value=self._fixtures.get(audio_reference)
  if value is None or not value.synthetic:raise LookupError("synthetic lip sync fixture unavailable")
  return value
 def audio_timing(self,audio_reference):return self.mouth_cue_sequence(audio_reference).duration_ms
 def viseme_timing(self,audio_reference):return self.mouth_cue_sequence(audio_reference).cues
