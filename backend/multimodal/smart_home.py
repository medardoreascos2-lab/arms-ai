"""Future smart-home capabilities represented as non-executable proposals."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
class SmartHomeCapability(str,Enum):LIGHT="LIGHT";HVAC="HVAC";CURTAIN="CURTAIN";TV="TV";SPEAKER="SPEAKER";APPLIANCE="APPLIANCE"
@dataclass(frozen=True)
class SmartHomeProposal:
 proposal_id:str;capability:SmartHomeCapability;device_reference:str;description:str;state:str="PROPOSED_ONLY";device_control_authorized:bool=False;execution_authorized:bool=False
 def __post_init__(self):
  if self.state!="PROPOSED_ONLY" or self.device_control_authorized or self.execution_authorized:raise ValueError("smart-home actions remain proposed only")
class SmartHomeCapabilityProvider(Protocol):
 def capabilities(self)->frozenset[SmartHomeCapability]:...
 def propose(self,capability:SmartHomeCapability,device_reference:str)->SmartHomeProposal:...
