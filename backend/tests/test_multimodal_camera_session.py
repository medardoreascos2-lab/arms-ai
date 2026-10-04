from datetime import datetime,timezone
import pytest
from backend.multimodal.camera_session import CameraSession,CameraSessionState
NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)
def test_camera_session_defaults_off_and_requires_permission_then_consent():
 s=CameraSession("camera-1","session-1","user-1","tenant-1","device-1");assert s.state==CameraSessionState.OFF
 p=s.transition(CameraSessionState.PERMISSION_REQUIRED,NOW)
 with pytest.raises(PermissionError):p.transition(CameraSessionState.ACTIVE,NOW)
 assert p.transition(CameraSessionState.ACTIVE,NOW,"consent-1").state==CameraSessionState.ACTIVE
def test_stopped_and_revoked_camera_sessions_are_terminal():
 active=CameraSession("c","s","u","t","d").transition(CameraSessionState.PERMISSION_REQUIRED,NOW).transition(CameraSessionState.ACTIVE,NOW,"consent")
 for terminal in (CameraSessionState.STOPPED,CameraSessionState.REVOKED):
  ended=active.transition(terminal,NOW)
  with pytest.raises(ValueError):ended.transition(CameraSessionState.ACTIVE,NOW,"consent")
