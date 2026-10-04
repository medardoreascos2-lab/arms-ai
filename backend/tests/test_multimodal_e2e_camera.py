from datetime import datetime, timezone

import pytest

from backend.multimodal.camera_frame import CameraFrame, FrameRetentionPolicy
from backend.multimodal.camera_policy import CameraCaptureController
from backend.multimodal.camera_session import CameraSession, CameraSessionState
from backend.multimodal.consent import ConsentState
from backend.multimodal.observable_context import ObservableContext, ObservableCue, ObservationValue

NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def controller(identifier):
    return CameraCaptureController(CameraSession(
        identifier, "session-1", "user-1", "tenant-1", "synthetic-device"
    ))


def frame(identifier):
    return CameraFrame(
        identifier, "camera-1", NOW, "image/jpeg", 16, 16,
        FrameRetentionPolicy.NO_STORAGE, "camera-consent", f"synthetic-frame:{identifier}",
    )


def observe(camera_frame, calls):
    calls.append(camera_frame.content_reference)
    return ObservableContext(
        observations={ObservableCue.PERSON_PRESENT: ObservationValue.TRUE},
        person_count=1,
        source_reference=camera_frame.content_reference,
        synthetic=True,
        limitations=("Synthetic frame metadata only.",),
    )


def activate(item):
    assert item.session.state is CameraSessionState.OFF
    item.request_start(explicit_user_action=True, at=NOW)
    item.activate(
        consent_state=ConsentState.GRANTED_SESSION,
        consent_reference="camera-consent",
        at=NOW,
    )
    assert item.visible_indicator is True


def test_synthetic_camera_start_capture_observe_stop_and_revoke_lifecycle():
    stopped = controller("camera-1")
    activate(stopped)
    capture_calls = []
    observation_calls = []
    captured = stopped.capture(lambda: (capture_calls.append("capture"), frame("one"))[1])
    context = observe(captured, observation_calls)
    assert context.synthetic is True
    assert capture_calls == ["capture"]
    assert observation_calls == ["synthetic-frame:one"]

    stopped.stop(NOW)
    assert stopped.session.state is CameraSessionState.STOPPED
    assert stopped.visible_indicator is False
    with pytest.raises(PermissionError):
        stopped.capture(lambda: (capture_calls.append("after-stop"), frame("two"))[1])
    assert capture_calls == ["capture"]
    assert observation_calls == ["synthetic-frame:one"]

    revoked = controller("camera-2")
    activate(revoked)
    revoked.revoke(NOW)
    assert revoked.session.state is CameraSessionState.REVOKED
    assert revoked.visible_indicator is False
    with pytest.raises(PermissionError):
        revoked.capture(lambda: (capture_calls.append("after-revoke"), frame("three"))[1])
    assert capture_calls == ["capture"]
    assert observation_calls == ["synthetic-frame:one"]