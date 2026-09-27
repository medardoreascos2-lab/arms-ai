from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_has_physical_test_readiness_method():
    text = source()

    assert "EvaluatePhysicalTestReadiness(" in text


def test_readiness_checks_connection_status():
    text = source()

    assert "selectedAccount.ConnectionStatus" in text
    assert "ConnectionStatus.Connected" in text


def test_connection_not_ready_marker_exists():
    text = source()

    assert "CONNECTION_NOT_READY" in text


def test_readiness_uses_native_trading_hours():
    text = source()

    assert "instrument.MasterInstrument.TradingHours" in text


def test_readiness_uses_session_iterator():
    text = source()

    assert "new SessionIterator(" in text


def test_readiness_uses_is_in_session():
    text = source()

    assert ".IsInSession(" in text


def test_market_closed_marker_exists():
    text = source()

    assert "MARKET_SESSION_CLOSED" in text


def test_unknown_marker_exists():
    text = source()

    assert "SESSION_STATE_UNKNOWN" in text


def test_ready_marker_exists():
    text = source()

    assert "PHYSICAL_TEST_READY" in text


def test_readiness_is_read_only():
    text = source()

    method_start = text.index(
        "EvaluatePhysicalTestReadiness("
    )

    method_end = text.index(
        "private ",
        method_start + 10
    )

    method = text[
        method_start:method_end
    ]

    assert "selectedAccount.Submit(" not in method
    assert "selectedAccount.Cancel(" not in method
    assert "selectedAccount.Flatten(" not in method
    assert "selectedAccount.CreateOrder(" not in method


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
