import inspect
from backend.multimodal.quiet_context import QuietState,quiet_decision
from backend.product.notifications import NotificationPriority
def test_noncritical_voice_and_avatar_are_queued_during_explicit_quiet_context():
 for state in (QuietState.QUIET_HOURS,QuietState.DO_NOT_DISTURB,QuietState.USER_MARKED_SLEEPING):
  d=quiet_decision(state,NotificationPriority.INFO);assert not d.voice_allowed and not d.avatar_allowed and d.queue_notification
def test_unknown_sleep_is_not_treated_as_sleep_and_no_camera_inference_exists():
 d=quiet_decision(QuietState.SLEEP_CONTEXT_UNKNOWN,NotificationPriority.INFO);assert d.voice_allowed and not d.queue_notification
 assert "camera" not in inspect.getsource(quiet_decision).lower()
