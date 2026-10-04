"""Truthful local handling for explicit emergency phrases."""
from dataclasses import dataclass
from .emergency import EmergencyIntent
@dataclass(frozen=True)
class EmergencySafetyResponse:
 intent:EmergencyIntent;priority:str="HIGHEST_LOCAL_PRIORITY";status:str="EMERGENCY_INTEGRATION_UNAVAILABLE";manual_instructions:tuple[str,...]=("Call local emergency services directly using your phone.","Move to a safer place if you can do so safely.","Ask a nearby person for immediate help.");external_action_taken:bool=False;dispatch_claimed:bool=False

def evaluate_emergency_phrase(text:str)->EmergencySafetyResponse|None:
 normalized=" ".join(text.lower().strip().split())
 if "llama al 911" in normalized or "call 911" in normalized:return EmergencySafetyResponse(EmergencyIntent.EXPLICIT_CALL_EMERGENCY_SERVICES)
 if "auxilio" in normalized or normalized in {"help me","help"}:return EmergencySafetyResponse(EmergencyIntent.EXPLICIT_HELP_REQUEST)
 return None
