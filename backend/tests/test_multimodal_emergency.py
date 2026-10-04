import pytest
from backend.multimodal.emergency import EmergencyIntent,EmergencySimulation,EmergencyState
def test_emergency_flow_is_confirmed_simulation_with_zero_external_authority():
 s=EmergencySimulation("e","t","u","s",EmergencyIntent.EXPLICIT_HELP_REQUEST).require_confirmation().confirm().simulate_dispatch();assert s.state==EmergencyState.SIMULATED_DISPATCH and not s.external_call_authorized and not s.external_message_authorized
def test_dispatch_cannot_be_simulated_without_explicit_confirmation():
 with pytest.raises(ValueError):EmergencySimulation("e","t","u","s",EmergencyIntent.POSSIBLE_SAFETY_EVENT).simulate_dispatch()
