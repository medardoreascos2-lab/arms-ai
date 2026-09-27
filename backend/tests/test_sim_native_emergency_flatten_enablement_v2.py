from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_entry_submit_remains_disabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_emergency_flatten_is_explicitly_enabled():
    text = source()

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )


def test_emergency_requires_simulator_provider():
    text = source()

    assert "Provider.Simulator" in text


def test_emergency_is_restricted_to_sim101():
    text = source()

    assert (
        "Emergency flatten is restricted to Sim101."
        in text
    )


def test_emergency_requires_operator_token():
    text = source()

    assert "EMERGENCY_FLATTEN_ARM_TOKEN" in text
    assert '"ARM_SIM_EMERGENCY_FLATTEN_V2"' in text


def test_emergency_requires_durable_permit():
    text = source()

    assert "EMERGENCY_FLATTEN_DURABLE_PERMIT" in text
    assert '"EMERGENCY_FLATTEN_SIM101_V2"' in text


def test_emergency_requires_single_use_consumption():
    text = source()

    assert "ConsumeEmergencyFlattenActivation();" in text
    assert ".consumed" in text


def test_cancel_is_target_instrument_scoped():
    text = source()

    assert "order.Instrument" in text
    assert "ReferenceEquals(" in text
    assert "selectedAccount.Cancel(" in text


def test_flatten_is_target_instrument_scoped():
    text = source()

    assert "selectedAccount.Flatten(" in text

    assert (
        "new List<NinjaTrader.Cbi.Instrument>"
        in text
    )


def test_no_change_order_surface_is_added():
    text = source()

    assert ".Change(" not in text
    assert "ChangeOrder(" not in text


def test_no_auto_retry():
    text = source()

    assert "AUTO_RETRY_ALLOWED = false" in text
