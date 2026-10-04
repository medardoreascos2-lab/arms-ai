"""Multimodal trust projection separating observations, inferences, and source classes."""
from dataclasses import dataclass
from enum import Enum
from .consent import ConsentState
from .domain import Modality
class EvidenceClass(str,Enum):OBSERVATION="OBSERVATION";INFERENCE="INFERENCE";USER_PROVIDED="USER_PROVIDED";DEVICE_PROVIDED="DEVICE_PROVIDED";SYNTHETIC="SYNTHETIC"
@dataclass(frozen=True)
class TrustEvidence:
 classification:EvidenceClass;statements:tuple[str,...]
@dataclass(frozen=True)
class MultimodalTrustProjection:
 source:str;modality:Modality;provider:str;confidence:float|None;consent_state:ConsentState;data_retention:str;limitations:tuple[str,...];what_was_observed:tuple[str,...];what_was_inferred:tuple[str,...];evidence:tuple[TrustEvidence,...]
 def __post_init__(self):
  if self.confidence is not None and not 0<=self.confidence<=1:raise ValueError("confidence out of range")
  if not self.limitations:raise ValueError("multimodal limitations required")
