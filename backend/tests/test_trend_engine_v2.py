from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from backend.models.candle import Candle
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.trend.trend_engine_v2 import (
    TrendEngineV2,
)


START_TIME = datetime(
    2026,
    7,
    27,
    20,
    0,
    tzinfo=timezone.utc,
)


def add_market_candles(
    *,
    store: LiveCandleStore,
    closes: list[float],
    symbol: str = "NQ",
    timeframe: str = "1M",
) -> None:

    for index, close in enumerate(
        closes
    ):
        store.add(
            Candle(
                symbol=symbol,
                timeframe=timeframe,
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=(
                    1000.0
                    + index
                ),
                timestamp=(
                    START_TIME
                    + timedelta(
                        minutes=index
                    )
                ),
            )
        )


def build_engine(
    *,
    store: LiveCandleStore,
) -> TrendEngineV2:
    return TrendEngineV2(
        live_candle_store=store,
        fast_period=10,
        slow_period=50,
        slope_lookback=5,
        sideways_threshold_percent=(
            0.0005
        ),
    )


def test_rejects_invalid_store():
    with pytest.raises(
        TypeError,
        match="live_candle_store",
    ):
        TrendEngineV2(
            live_candle_store=object(),
        )


def test_returns_insufficient_data():
    store = LiveCandleStore()

    add_market_candles(
        store=store,
        closes=[
            23000.0
            + index
            for index in range(20)
        ],
    )

    result = build_engine(
        store=store
    ).analyze(
        symbol="NQ",
        timeframe="1M",
    )

    assert (
        result["status"]
        == "INSUFFICIENT_DATA"
    )

    assert (
        result["direction"]
        == "INSUFFICIENT_DATA"
    )

    assert result["candle_count"] == 20
    assert result["required_candles"] == 50
    assert result["confidence"] == 0.0


def test_detects_bullish_trend():
    store = LiveCandleStore()

    add_market_candles(
        store=store,
        closes=[
            23000.0
            + (
                index
                * 2.0
            )
            for index in range(60)
        ],
    )

    result = build_engine(
        store=store
    ).analyze(
        symbol="NQ",
        timeframe="1M",
    )

    assert result["status"] == "READY"
    assert result["direction"] == "BULLISH"
    assert result["fast_ema"] > result["slow_ema"]
    assert result["slope"] > 0
    assert (
        result["current_price"]
        > result["slow_ema"]
    )
    assert 0.0 <= result["confidence"] <= 1.0


def test_detects_bearish_trend():
    store = LiveCandleStore()

    add_market_candles(
        store=store,
        closes=[
            23200.0
            - (
                index
                * 2.0
            )
            for index in range(60)
        ],
    )

    result = build_engine(
        store=store
    ).analyze(
        symbol="NQ",
        timeframe="1M",
    )

    assert result["status"] == "READY"
    assert result["direction"] == "BEARISH"
    assert result["fast_ema"] < result["slow_ema"]
    assert result["slope"] < 0
    assert (
        result["current_price"]
        < result["slow_ema"]
    )
    assert 0.0 <= result["confidence"] <= 1.0


def test_detects_sideways_market():
    store = LiveCandleStore()

    add_market_candles(
        store=store,
        closes=[
            23000.0
            for _ in range(60)
        ],
    )

    result = build_engine(
        store=store
    ).analyze(
        symbol="NQ",
        timeframe="1M",
    )

    assert result["status"] == "READY"
    assert result["direction"] == "SIDEWAYS"
    assert result["fast_ema"] == 23000.0
    assert result["slow_ema"] == 23000.0
    assert result["slope"] == 0.0
    assert result["confidence"] == 1.0


def test_keeps_markets_separated():
    store = LiveCandleStore()

    add_market_candles(
        store=store,
        symbol="NQ",
        timeframe="1M",
        closes=[
            23000.0
            + index
            for index in range(60)
        ],
    )

    add_market_candles(
        store=store,
        symbol="ES",
        timeframe="5M",
        closes=[
            6200.0
            - index
            for index in range(60)
        ],
    )

    engine = build_engine(
        store=store
    )

    nq = engine.analyze(
        symbol="NQ",
        timeframe="1M",
    )

    es = engine.analyze(
        symbol="ES",
        timeframe="5M",
    )

    assert nq["direction"] == "BULLISH"
    assert es["direction"] == "BEARISH"


def test_normalizes_symbol_and_timeframe():
    store = LiveCandleStore()

    add_market_candles(
        store=store,
        symbol="NQ",
        timeframe="1M",
        closes=[
            23000.0
            + index
            for index in range(60)
        ],
    )

    result = build_engine(
        store=store
    ).analyze(
        symbol=" nq ",
        timeframe=" 1m ",
    )

    assert result["symbol"] == "NQ"
    assert result["timeframe"] == "1M"
    assert result["direction"] == "BULLISH"
