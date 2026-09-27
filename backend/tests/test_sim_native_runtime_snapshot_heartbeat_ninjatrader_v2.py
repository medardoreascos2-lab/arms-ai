from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def heartbeat_body(text):
    start = text.index(
        "private void OnRuntimeSnapshotHeartbeat("
    )

    next_method = text.index(
        "\n        private ",
        start + 1,
    )

    return text[start:next_method]


def test_bridge_uses_dispatcher_timer_for_runtime_snapshot():
    text = source()

    assert (
        "using System.Windows.Threading;"
        in text
    )

    assert (
        "private DispatcherTimer "
        "runtimeSnapshotTimer;"
        in text
    )


def test_runtime_snapshot_heartbeat_interval_is_five_seconds():
    text = source()

    assert (
        "Interval = TimeSpan.FromSeconds(5)"
        in text
    )


def test_runtime_snapshot_heartbeat_starts_in_realtime():
    text = source()

    realtime = text.index(
        "State == State.Realtime"
    )

    start = text.index(
        "StartRuntimeSnapshotHeartbeat();"
    )

    assert realtime < start


def test_runtime_snapshot_heartbeat_refreshes_snapshot():
    text = source()

    body = heartbeat_body(text)

    assert (
        "WriteRuntimeReadinessSnapshot();"
        in body
    )


def test_runtime_snapshot_heartbeat_has_no_execution_surface():
    text = source()

    body = heartbeat_body(text)

    forbidden = (
        "CreateOrder(",
        ".Submit(",
        ".Cancel(",
        ".Change(",
        ".Flatten(",
        "CancelAllOrders",
        "AttemptOneShotSubmit(",
        "AttemptEmergencyFlatten(",
        "ConsumeSubmitActivation(",
        "ReadActivationEvidence(",
    )

    for token in forbidden:
        assert token not in body


def test_runtime_snapshot_timer_is_cleaned_up_on_termination():
    text = source()

    assert (
        "StopRuntimeSnapshotHeartbeat();"
        in text
    )

    assert (
        "runtimeSnapshotTimer.Stop();"
        in text
    )

    assert (
        "runtimeSnapshotTimer.Tick -="
        in text
    )

    assert (
        "OnRuntimeSnapshotHeartbeat;"
        in text
    )

    assert (
        "runtimeSnapshotTimer = null;"
        in text
    )


def test_runtime_snapshot_heartbeat_preserves_hard_safety_constants():
    text = source()

    assert (
        "NATIVE_SUBMIT_ENABLED = false"
        in text
    )

    assert (
        "AUTO_RETRY_ALLOWED = false"
        in text
    )
