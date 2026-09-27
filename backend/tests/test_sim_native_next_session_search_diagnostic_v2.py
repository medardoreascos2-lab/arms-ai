from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(encoding="utf-8")


def test_has_next_session_search_diagnostic():
    text = source()

    assert "ARMS_SIM_NEXT_SESSION_SEARCH" in text


def test_searches_multiple_candidate_days():
    text = source()

    assert "candidateDay" in text
    assert "AddDays(" in text


def test_search_logs_offset():
    text = source()

    assert '" day_offset="' in text


def test_search_logs_candidate_time():
    text = source()

    assert '" candidate="' in text


def test_search_logs_found():
    text = source()

    assert '" found="' in text


def test_search_logs_begin_end():
    text = source()

    assert '" begin="' in text
    assert '" end="' in text


def test_search_is_read_only():
    text = source()

    marker = text.index(
        "ARMS_SIM_NEXT_SESSION_SEARCH"
    )

    nearby = text[
        max(0, marker - 3000):
        marker + 5000
    ]

    assert "selectedAccount.Submit(" not in nearby
    assert "selectedAccount.Cancel(" not in nearby
    assert "selectedAccount.Flatten(" not in nearby
    assert "selectedAccount.CreateOrder(" not in nearby


def test_entry_remains_disabled():
    text = source()

    assert "NATIVE_SUBMIT_ENABLED = false" in text


def test_emergency_remains_enabled():
    text = source()

    assert (
        "NATIVE_EMERGENCY_FLATTEN_ENABLED = true"
        in text
    )
