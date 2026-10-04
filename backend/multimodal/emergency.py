"""Simulation-only emergency intent state machine; no external dispatch."""
from dataclasses import dataclass,replace
from enum import Enum
class EmergencyIntent(str,Enum):EXPLICIT_HELP_REQUEST="EXPLICIT_HELP_REQUEST";EXPLICIT_CALL_EMERGENCY_SERVICES="EXPLICIT_CALL_EMERGENCY_SERVICES";EXPLICIT_CONTACT_EMERGENCY_PERSON="EXPLICIT_CONTACT_EMERGENCY_PERSON";POSSIBLE_SAFETY_EVENT="POSSIBLE_SAFETY_EVENT"
class EmergencyState(str,Enum):DETECTED="DETECTED";CONFIRMATION_REQUIRED="CONFIRMATION_REQUIRED";CONFIRMED="CONFIRMED";SIMULATED_DISPATCH="SIMULATED_DISPATCH";CANCELLED="CANCELLED";UNAVAILABLE="UNAVAILABLE"
@dataclass(frozen=True)
class EmergencySimulation:
 simulation_id:str;tenant_id:str;user_id:str;session_id:str;intent:EmergencyIntent;state:EmergencyState=EmergencyState.DETECTED;external_call_authorized:bool=False;external_message_authorized:bool=False
 def require_confirmation(self):
  if self.state!=EmergencyState.DETECTED:raise ValueError("confirmation may only follow detection")
  return replace(self,state=EmergencyState.CONFIRMATION_REQUIRED)
 def confirm(self):
  if self.state!=EmergencyState.CONFIRMATION_REQUIRED:raise ValueError("explicit confirmation required")
  return replace(self,state=EmergencyState.CONFIRMED)
 def simulate_dispatch(self):
  if self.state!=EmergencyState.CONFIRMED:raise ValueError("confirmed simulation required")
  return replace(self,state=EmergencyState.SIMULATED_DISPATCH)
 def cancel(self):
  if self.state in {EmergencyState.SIMULATED_DISPATCH,EmergencyState.CANCELLED}:raise ValueError("simulation already terminal")
  return replace(self,state=EmergencyState.CANCELLED)
