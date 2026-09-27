from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_has_session_diagnostic_marker():
    text = source()

    assert "ARMS_SIM_SESSION_WINDOW_DIAGNOSTIC" in text


def test_diagnostic_prints_trading_hours_name():
    text = source()

    assert '" trading_hours="' in text
    assert "tradingHours.Name" in text


def test_diagnostic_prints_timezone():
    text = source()

    assert '" application_timezone="' in text
    assert '" trading_hours_timezone="' in text
    assert "tradingHours.TimeZone" in text


def test_diagnostic_prints_application_now():
    text = source()

    assert '" application_now="' in text
    assert '" now_local="' not in text


def test_diagnostic_prints_is_in_session():
    text = source()

    assert '" is_in_session="' in text


def test_diagnostic_prints_get_next_session_result():
    text = source()

    assert '" next_session_found="' in text


def test_diagnostic_prints_actual_begin_end():
    text = source()

    assert '" session_begin="' in text
    assert '" session_end="' in text


def test_entry_stays_disabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_emergency_stays_enabled():
    text = source()

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )
