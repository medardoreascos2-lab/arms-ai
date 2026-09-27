from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_has_readiness_output_marker():
    text = source()

    assert "ARMS_SIM_PHYSICAL_TEST_READINESS" in text


def test_readiness_output_has_status():
    text = source()

    assert '" status="' in text


def test_readiness_output_has_instrument():
    text = source()

    assert '" instrument="' in text


def test_readiness_output_has_connection():
    text = source()

    assert '" connection="' in text


def test_readiness_output_calls_evaluator():
    text = source()

    assert "EvaluatePhysicalTestReadiness(" in text


def test_readiness_output_resolves_instrument():
    text = source()

    assert (
        "NinjaTrader.Cbi.Instrument.GetInstrument("
        in text
    )


def test_output_does_not_require_execution_requests():
    text = source()

    marker = text.index(
        "ARMS_SIM_PHYSICAL_TEST_READINESS"
    )

    request_submit = text.index(
        "if (RequestOneShotSubmit)"
    )

    request_flatten = text.index(
        "if (RequestEmergencyFlatten)"
    )

    assert marker < request_submit
    assert marker < request_flatten


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
