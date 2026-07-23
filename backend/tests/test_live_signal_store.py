import pytest

from backend.services.live_signal_store import (
    LiveSignalStore,
)


def build_signal(
    *,
    symbol="NQ",
    timeframe="5m",
    action="BUY",
):
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "action": action,
        "approved": True,
        "score": 88.0,
        "grade": "A+",
        "probability": 84.0,
        "entry_price": 21691.0,
        "stop_loss": 21672.25,
        "take_profit": 21728.50,
    }


def test_store_signal():
    store = LiveSignalStore()

    store.save(
        build_signal()
    )

    signal = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert signal is not None
    assert signal["action"] == "BUY"


def test_replace_previous_signal():
    store = LiveSignalStore()

    store.save(
        build_signal(
            action="BUY"
        )
    )

    store.save(
        build_signal(
            action="SELL"
        )
    )

    signal = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert signal["action"] == "SELL"


def test_keep_markets_separated():
    store = LiveSignalStore()

    store.save(
        build_signal(
            symbol="NQ"
        )
    )

    store.save(
        build_signal(
            symbol="ES"
        )
    )

    assert (
        store.get_latest(
            symbol="NQ",
            timeframe="5m",
        )["symbol"]
        == "NQ"
    )

    assert (
        store.get_latest(
            symbol="ES",
            timeframe="5m",
        )["symbol"]
        == "ES"
    )


def test_missing_signal_returns_none():
    store = LiveSignalStore()

    assert (
        store.get_latest(
            symbol="NQ",
            timeframe="5m",
        )
        is None
    )


def test_returns_copy():
    store = LiveSignalStore()

    store.save(
        build_signal()
    )

    signal = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    signal["action"] = "WAIT"

    latest = store.get_latest(
        symbol="NQ",
        timeframe="5m",
    )

    assert latest["action"] == "BUY"
