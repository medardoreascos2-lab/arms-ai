"""Provider-neutral creative media seams; no generator is installed or purchased."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol
class CreativeCapability(str,Enum):IMAGE_GENERATION="IMAGE_GENERATION";VIDEO_GENERATION="VIDEO_GENERATION";IMAGE_TO_VIDEO="IMAGE_TO_VIDEO";STORYBOARD="STORYBOARD";AVATAR_ANIMATION="AVATAR_ANIMATION"
@dataclass(frozen=True)
class CreativeRequest:
 request_id:str;tenant_id:str;user_id:str;session_id:str;capability:CreativeCapability;prompt_reference:str;source_media_reference:str|None=None
@dataclass(frozen=True)
class CreativeResult:
 request_id:str;status:str="INTEGRATION_PENDING";output_reference:None=None;provider:None=None;external_purchase_authorized:bool=False
class CreativeMultimodalProvider(Protocol):
 def generate(self,request:CreativeRequest)->CreativeResult:...
