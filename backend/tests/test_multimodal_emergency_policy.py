from backend.multimodal.emergency import EmergencyIntent
from backend.multimodal.emergency_policy import evaluate_emergency_phrase
def test_explicit_spanish_help_and_911_requests_get_highest_truthful_priority():
 for phrase,intent in (("auxilio",EmergencyIntent.EXPLICIT_HELP_REQUEST),("llama al 911",EmergencyIntent.EXPLICIT_CALL_EMERGENCY_SERVICES)):
  r=evaluate_emergency_phrase(phrase);assert r.intent==intent and r.priority=="HIGHEST_LOCAL_PRIORITY" and r.status=="EMERGENCY_INTEGRATION_UNAVAILABLE";assert not r.external_action_taken and not r.dispatch_claimed and r.manual_instructions
def test_nonemergency_text_does_not_create_emergency_action():assert evaluate_emergency_phrase("show my daily summary") is None
