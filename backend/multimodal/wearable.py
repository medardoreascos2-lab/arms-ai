"""Wearable metric seam with explicit provenance and no diagnosis."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
class WearableMetric(str,Enum):HEART_RATE="heart_rate";STEPS="steps";ACTIVITY="activity";SLEEP="sleep";SPO2="spo2";HRV="hrv";TEMPERATURE="temperature";BLOOD_PRESSURE="blood_pressure"
class WearableDataStatus(str,Enum):VERIFIED_DEVICE_DATA="VERIFIED_DEVICE_DATA";USER_REPORTED="USER_REPORTED";UNKNOWN="UNKNOWN"
@dataclass(frozen=True)
class WearableObservation:
 tenant_id:str;user_id:str;metric:WearableMetric;value:float|str|None;unit:str|None;observed_at:datetime|None;status:WearableDataStatus;source_reference:str|None;diagnosis_provided:bool=False
 def __post_init__(self):
  if self.diagnosis_provided:raise ValueError("wearable observations cannot diagnose")
  if self.status==WearableDataStatus.UNKNOWN and (self.value is not None or self.observed_at is not None):raise ValueError("unknown wearable data cannot claim a value")
  if self.status==WearableDataStatus.VERIFIED_DEVICE_DATA and not self.source_reference:raise ValueError("verified device data requires source")
