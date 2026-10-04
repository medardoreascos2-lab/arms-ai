from datetime import datetime,timezone
import pytest
from backend.multimodal.camera_policy import CameraCaptureController
from backend.multimodal.camera_session import CameraSession,CameraSessionState
from backend.multimodal.consent import ConsentState
NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)
def controller():return CameraCaptureController(CameraSession("c","s","u","t","d"))
def test_camera_requires_explicit_start_consent_and_visible_indicator():
 c=controller()
 with pytest.raises(PermissionError):c.request_start(explicit_user_action=False,at=NOW)
 c.request_start(explicit_user_action=True,at=NOW)
 with pytest.raises(PermissionError):c.activate(consent_state=ConsentState.DENIED,consent_reference="x",at=NOW)
 c.activate(consent_state=ConsentState.GRANTED_SESSION,consent_reference="consent",at=NOW);assert c.visible_indicator and c.capture(lambda:"frame")=="frame"
def test_stop_and_revoke_prevent_all_additional_capture():
 for action in ("stop","revoke"):
  c=controller();c.request_start(explicit_user_action=True,at=NOW);c.activate(consent_state=ConsentState.GRANTED_SESSION,consent_reference="consent",at=NOW);getattr(c,action)(NOW);calls=0
  def capture():
   nonlocal calls;calls+=1
  with pytest.raises(PermissionError):c.capture(capture)
  assert calls==0 and not c.visible_indicator
