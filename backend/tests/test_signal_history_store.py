from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services.signal_history_store import (
    SignalHistoryStore,
)


def build_signal(
    *,
    index: int = 0,
    symbol: str = "NQ",
    timeframe: str = "5m",
    action: str = "BUY",
) -> dict[str, object]:
    timestamp = (
        datetime(
            2026,
            7,
            22,
            9,
            30,
            tzinfo=timezone.utc,
        )
        + timedelta(
            minutes=index * 5
        )
    )

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "approved": action != "WAIT",
        "score": 88.0 - index,
        "grade": "A+",
        "probability": 84.0,
        "confidence": "MUY ALTA",
        "risk_approved": True,
        "entry_price": 21691.0 + index,
        "stop_loss": 21672.25 + index,
        "take_profit": 21728.50 + index,
        "reason": "Señal de prueba.",
        "generated_at": timestamp,
    }


def test_appends_and_returns_signal_history():
    store = SignalHistoryStore()

    for index in range(3):
        store.append(
            build_signal(
                index=index
            )
        )

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 3
    assert (
        result[0]["generated_at"]
        < result[1]["generated_at"]
        < result[2]["generated_at"]
    )


def test_returns_latest_requested_signals():
    store = SignalHistoryStore()

    for index in range(5):
        store.append(
            build_signal(
                index=index
            )
        )

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=2,
    )

    assert len(result) == 2
    assert result[0]["entry_price"] == 21694.0
    assert result[1]["entry_price"] == 21695.0


def test_keeps_markets_separated():
    store = SignalHistoryStore()

    store.append(
        build_signal(
            symbol="NQ",
            timeframe="5m",
        )
    )

    store.append(
        build_signal(
            symbol="ES",
            timeframe="1m",
        )
    )

    nq = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    es = store.get_history(
        symbol="ES",
        timeframe="1m",
        limit=10,
    )

    assert len(nq) == 1
    assert len(es) == 1
    assert nq[0]["symbol"] == "NQ"
    assert es[0]["symbol"] == "ES"


def test_replaces_duplicate_generated_at():
    store = SignalHistoryStore()

    original = build_signal(
        index=0,
        action="BUY",
    )

    replacement = {
        **build_signal(
            index=0,
            action="SELL",
        ),
        "score": 91.0,
    }

    store.append(original)
    store.append(replacement)

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 1
    assert result[0]["action"] == "SELL"
    assert result[0]["score"] == 91.0


def test_limits_history_per_market():
    store = SignalHistoryStore(
        max_signals=3
    )

    for index in range(5):
        store.append(
            build_signal(
                index=index
            )
        )

    result = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 3
    assert result[0]["entry_price"] == 21693.0
    assert result[-1]["entry_price"] == 21695.0


def test_returns_defensive_copies():
    store = SignalHistoryStore()

    store.append(
        build_signal()
    )

    first = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    first[0]["action"] = "WAIT"

    second = store.get_history(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert second[0]["action"] == "BUY"


def test_rejects_invalid_limit():
    store = SignalHistoryStore()

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        store.get_history(
            symbol="NQ",
            timeframe="5m",
            limit=0,
        )


def test_rejects_invalid_max_signals():
    with pytest.raises(
        ValueError,
        match="max_signals",
    ):
        SignalHistoryStore(
            max_signals=0
        )
