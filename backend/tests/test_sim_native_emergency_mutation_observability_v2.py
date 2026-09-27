from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_cancel_logs_before_native_call():
    text = source()

    marker = text.index(
        "ARMS_SIM_EMERGENCY_CANCEL_CALL"
    )

    call = text.index(
        "selectedAccount.Cancel("
    )

    assert marker < call


def test_cancel_logs_order_count():
    text = source()

    assert "activeOrders.Count" in text


def test_flatten_logs_before_native_call():
    text = source()

    marker = text.index(
        "ARMS_SIM_EMERGENCY_FLATTEN_CALL"
    )

    call = text.index(
        "selectedAccount.Flatten("
    )

    assert marker < call


def test_flatten_logs_exact_instrument():
    text = source()

    assert "InstrumentName.Trim()" in text


def test_already_flat_logs_no_native_mutation():
    text = source()

    assert (
        "ARMS_SIM_EMERGENCY_ALREADY_FLAT_NO_MUTATION"
        in text
    )


def test_entry_remains_disabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_emergency_remains_enabled():
    text = source()

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )


def test_auto_retry_remains_disabled():
    text = source()

    assert "AUTO_RETRY_ALLOWED = false" in text
