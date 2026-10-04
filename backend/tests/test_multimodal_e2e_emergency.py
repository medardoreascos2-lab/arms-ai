from backend.multimodal.emergency import EmergencyIntent, EmergencySimulation, EmergencyState
from backend.multimodal.emergency_policy import evaluate_emergency_phrase


def assert_no_external_action(value):
    if hasattr(value, "external_action_taken"):
        assert value.external_action_taken is False
        assert value.dispatch_claimed is False
    else:
        assert value.external_call_authorized is False
        assert value.external_message_authorized is False


def test_explicit_help_and_911_requests_are_high_priority_but_integration_unavailable():
    cases = (
        ("help me", EmergencyIntent.EXPLICIT_HELP_REQUEST),
        ("call 911", EmergencyIntent.EXPLICIT_CALL_EMERGENCY_SERVICES),
    )
    for phrase, intent in cases:
        response = evaluate_emergency_phrase(phrase)
        assert response.intent is intent
        assert response.priority == "HIGHEST_LOCAL_PRIORITY"
        assert response.status == "EMERGENCY_INTEGRATION_UNAVAILABLE"
        assert response.manual_instructions
        assert_no_external_action(response)


def test_possible_inferred_event_requires_confirmation_and_never_auto_dispatches():
    simulation = EmergencySimulation(
        "inferred-1", "tenant-1", "user-1", "session-1",
        EmergencyIntent.POSSIBLE_SAFETY_EVENT,
    ).require_confirmation()
    assert simulation.state is EmergencyState.CONFIRMATION_REQUIRED
    assert_no_external_action(simulation)


def test_false_positive_and_cancel_end_without_external_action():
    assert evaluate_emergency_phrase("The chart fell below its moving average") is None
    cancelled = EmergencySimulation(
        "cancel-1", "tenant-1", "user-1", "session-1",
        EmergencyIntent.POSSIBLE_SAFETY_EVENT,
    ).require_confirmation().cancel()
    assert cancelled.state is EmergencyState.CANCELLED
    assert_no_external_action(cancelled)


def test_confirmed_dispatch_remains_explicitly_simulated_and_local_only():
    simulated = EmergencySimulation(
        "simulation-1", "tenant-1", "user-1", "session-1",
        EmergencyIntent.EXPLICIT_CALL_EMERGENCY_SERVICES,
    ).require_confirmation().confirm().simulate_dispatch()
    assert simulated.state is EmergencyState.SIMULATED_DISPATCH
    assert_no_external_action(simulated)