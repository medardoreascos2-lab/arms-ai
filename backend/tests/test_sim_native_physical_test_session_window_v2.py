from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_has_session_window_method():
    text = source()

    assert "DescribePhysicalTestSessionWindow(" in text


def test_uses_native_session_iterator():
    text = source()

    assert "new SessionIterator(" in text


def test_uses_get_next_session():
    text = source()

    assert ".GetNextSession(" in text


def test_reads_actual_session_begin():
    text = source()

    assert ".ActualSessionBegin" in text


def test_reads_actual_session_end():
    text = source()

    assert ".ActualSessionEnd" in text


def test_output_has_session_begin():
    text = source()

    assert '" session_begin="' in text


def test_output_has_session_end():
    text = source()

    assert '" session_end="' in text


def test_unknown_window_is_fail_closed():
    text = source()

    assert "SESSION_WINDOW_UNKNOWN" in text


def test_session_window_is_read_only():
    text = source()

    start = text.index(
        "DescribePhysicalTestSessionWindow("
    )

    end = text.index(
        "private ",
        start + 10
    )

    method = text[start:end]

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
