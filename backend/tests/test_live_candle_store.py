from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.models.candle import Candle


def build_candle(
    *,
    index: int,
    symbol: str = "NQ",
    timeframe: str = "5m",
) -> Candle:
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

    base = 21600.0 + index

    return Candle(
        symbol=symbol,
        timeframe=timeframe,
        open=base,
        high=base + 4.0,
        low=base - 2.0,
        close=base + 2.0,
        volume=1000.0 + index,
        timestamp=timestamp,
    )


def test_adds_and_returns_latest_candles():
    store = LiveCandleStore(
        max_candles=10
    )

    for index in range(5):
        store.add(
            build_candle(index=index)
        )

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=3,
    )

    assert len(result) == 3
    assert result[0].timestamp < result[1].timestamp
    assert result[1].timestamp < result[2].timestamp
    assert result[-1].close == 21606.0


def test_replaces_duplicate_timestamp():
    store = LiveCandleStore(
        max_candles=10
    )

    original = build_candle(
        index=1
    )

    replacement = Candle(
        symbol=original.symbol,
        timeframe=original.timeframe,
        open=original.open,
        high=original.high + 5.0,
        low=original.low,
        close=original.close + 3.0,
        volume=original.volume + 50.0,
        timestamp=original.timestamp,
    )

    store.add(original)
    store.add(replacement)

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 1
    assert result[0].close == replacement.close
    assert result[0].high == replacement.high


def test_limits_candles_per_market():
    store = LiveCandleStore(
        max_candles=3
    )

    for index in range(5):
        store.add(
            build_candle(index=index)
        )

    result = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    assert len(result) == 3
    assert result[0].timestamp == build_candle(
        index=2
    ).timestamp
    assert result[-1].timestamp == build_candle(
        index=4
    ).timestamp


def test_keeps_markets_separated():
    store = LiveCandleStore(
        max_candles=10
    )

    store.add(
        build_candle(
            index=0,
            symbol="NQ",
            timeframe="5m",
        )
    )

    store.add(
        build_candle(
            index=0,
            symbol="ES",
            timeframe="1m",
        )
    )

    nq = store.get_latest(
        symbol="NQ",
        timeframe="5m",
        limit=10,
    )

    es = store.get_latest(
        symbol="ES",
        timeframe="1m",
        limit=10,
    )

    assert len(nq) == 1
    assert len(es) == 1
    assert nq[0].symbol == "NQ"
    assert es[0].symbol == "ES"


def test_rejects_invalid_limit():
    store = LiveCandleStore()

    with pytest.raises(
        ValueError,
        match="limit",
    ):
        store.get_latest(
            symbol="NQ",
            timeframe="5m",
            limit=0,
        )


def test_rejects_invalid_max_candles():
    with pytest.raises(
        ValueError,
        match="max_candles",
    ):
        LiveCandleStore(
            max_candles=0
        )
