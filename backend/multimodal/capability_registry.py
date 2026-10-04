"""Registry advertises only verified model and device capabilities."""
from dataclasses import dataclass
from enum import Enum
class MultimodalCapability(str,Enum):TEXT_GENERATION="TEXT_GENERATION";VISION="VISION";STT="STT";TTS="TTS";IMAGE_GENERATION="IMAGE_GENERATION";VIDEO_GENERATION="VIDEO_GENERATION";LIP_SYNC="LIP_SYNC"
class CapabilityState(str,Enum):AVAILABLE="AVAILABLE";UNAVAILABLE="UNAVAILABLE";LOCAL_TEST_ONLY="LOCAL_TEST_ONLY";INTEGRATION_PENDING="INTEGRATION_PENDING"
@dataclass(frozen=True)
class CapabilityRecord:
 provider_id:str;capability:MultimodalCapability;state:CapabilityState;model_id:str|None=None;digest:str|None=None;limitations:tuple[str,...]=()
class CapabilityRegistry:
 def __init__(self,records:tuple[CapabilityRecord,...]):self._records={(r.provider_id,r.capability):r for r in records}
 def get(self,provider_id,capability):return self._records.get((provider_id,capability),CapabilityRecord(provider_id,capability,CapabilityState.UNAVAILABLE,limitations=("Capability not registered.",)))
def validated_local_registry():
 qwen="qwen3.5:9b-q4_K_M";digest="sha256:56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90"
 records=[CapabilityRecord("ollama-local",MultimodalCapability.TEXT_GENERATION,CapabilityState.AVAILABLE,qwen,digest,("Tool support unavailable.",))]
 records.extend(CapabilityRecord("ollama-local",cap,CapabilityState.UNAVAILABLE,qwen,digest,("Not validated for this local model.",)) for cap in MultimodalCapability if cap!=MultimodalCapability.TEXT_GENERATION)
 records.extend((CapabilityRecord("synthetic-stt",MultimodalCapability.STT,CapabilityState.LOCAL_TEST_ONLY),CapabilityRecord("synthetic-tts",MultimodalCapability.TTS,CapabilityState.LOCAL_TEST_ONLY),CapabilityRecord("synthetic-vision",MultimodalCapability.VISION,CapabilityState.LOCAL_TEST_ONLY),CapabilityRecord("synthetic-lip-sync",MultimodalCapability.LIP_SYNC,CapabilityState.LOCAL_TEST_ONLY)))
 return CapabilityRegistry(tuple(records))
