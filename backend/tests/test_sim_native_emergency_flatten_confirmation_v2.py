from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_subscribes_to_position_update():
    text = source()

    assert "selectedAccount.PositionUpdate +=" in text


def test_unsubscribes_from_position_update():
    text = source()

    assert "selectedAccount.PositionUpdate -=" in text


def test_has_native_position_update_handler():
    text = source()

    assert "OnNativePositionUpdate" in text
    assert "PositionEventArgs" in text


def test_flatten_tracks_pending_confirmation():
    text = source()

    assert "emergencyFlattenAwaitingConfirmation" in text


def test_flatten_tracks_target_instrument():
    text = source()

    assert "emergencyFlattenInstrumentName" in text


def test_pending_marker_exists():
    text = source()

    assert (
        "ARMS_SIM_EMERGENCY_FLATTEN_PENDING_CONFIRMATION"
        in text
    )


def test_confirmed_marker_exists():
    text = source()

    assert (
        "ARMS_SIM_EMERGENCY_FLATTEN_CONFIRMED"
        in text
    )


def test_confirmation_requires_flat_position():
    text = source()

    assert "MarketPosition.Flat" in text


def test_confirmation_is_instrument_scoped():
    text = source()

    assert "position.Instrument" in text
    assert "emergencyFlattenInstrumentName" in text


def test_pending_state_is_set_before_flatten_call():
    text = source()

    pending = text.index(
        "emergencyFlattenAwaitingConfirmation"
    )

    pending_true = text.index(
        "true;",
        pending
    )

    call = text.index(
        "selectedAccount.Flatten("
    )

    assert pending < pending_true < call


def test_pending_marker_is_before_flatten_call():
    text = source()

    marker = text.index(
        "ARMS_SIM_EMERGENCY_FLATTEN_PENDING_CONFIRMATION"
    )

    call = text.index(
        "selectedAccount.Flatten("
    )

    assert marker < call


def test_entry_remains_disabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_emergency_remains_enabled():
    text = source()

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )


def test_no_auto_retry():
    text = source()

    assert "AUTO_RETRY_ALLOWED = false" in text
