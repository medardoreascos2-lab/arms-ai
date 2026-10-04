"""Conservative observable human context; diagnoses and sensitive traits are absent."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping

class ObservableCue(str,Enum):
 PERSON_PRESENT="person_present";PERSON_COUNT="person_count";SITTING="sitting";STANDING="standing";MOVING="moving";NOT_MOVING="not_moving";EYES_VISIBLE="eyes_visible";EYES_APPARENTLY_CLOSED="eyes_apparently_closed";SPEAKING="speaking";UNKNOWN="unknown"
class ObservationValue(str,Enum): TRUE="TRUE";FALSE="FALSE";UNKNOWN="UNKNOWN"

@dataclass(frozen=True)
class ObservableContext:
 observations:Mapping[ObservableCue,ObservationValue];person_count:int|None;source_reference:str;synthetic:bool;limitations:tuple[str,...]
 def __post_init__(self):
  if self.person_count is not None and self.person_count<0:raise ValueError("person count cannot be negative")
  if any(not isinstance(k,ObservableCue) or not isinstance(v,ObservationValue) for k,v in self.observations.items()):raise ValueError("only conservative observable cues are permitted")
  object.__setattr__(self,"observations",MappingProxyType(dict(self.observations)))
