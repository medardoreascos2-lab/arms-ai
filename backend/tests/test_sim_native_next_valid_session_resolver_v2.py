from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_has_next_valid_session_resolver():
    text = source()

    assert "ResolveNextPhysicalTestSessionWindow(" in text


def test_resolver_searches_multiple_days():
    text = source()

    assert "dayOffset" in text
    assert "AddDays(" in text


def test_resolver_uses_get_next_session():
    text = source()

    assert ".GetNextSession(" in text


def test_resolver_returns_first_valid_session():
    text = source()

    assert "return" in text
    assert "next_session_begin=" in text
    assert "next_session_end=" in text


def test_resolver_has_unknown_fallback():
    text = source()

    assert "NEXT_SESSION_UNKNOWN" in text


def test_readiness_output_has_next_session_begin():
    text = source()

    assert '" next_session_begin="' in text


def test_readiness_output_has_next_session_end():
    text = source()

    assert '" next_session_end="' in text


def test_resolver_is_read_only():
    text = source()

    start = text.index(
        "ResolveNextPhysicalTestSessionWindow("
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
