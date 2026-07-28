from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from backend.context.market_context_engine_v2 import (
    MarketContextEngineV2,
)
from backend.models.candle import Candle


START_TIME = datetime(
    2026,
    7,
    27,
    20,
    0,
    tzinfo=timezone.utc,
)


def build_candles(
    closes: list[float],
) -> list[Candle]:
    candles = []

    for index, close in enumerate(
        closes
    ):
        candles.append(
            Candle(
                symbol="NQ",
                timeframe="5M",
                open=close,
                high=close + 2.0,
                low=close - 2.0,
                close=close,
                volume=1000.0,
                timestamp=(
                    START_TIME
                    + timedelta(
                        minutes=index * 5
                    )
                ),
            )
        )

    return candles


def build_engine():
    return MarketContextEngineV2(
        minimum_candles=5,
        internal_range_lookback=5,
        near_extreme_threshold=0.10,
        equilibrium_tolerance=0.05,
        decision_threshold=0.25,
    )


def test_detects_buy_context_in_discount():
    candles = build_candles(
        [
            100.0,
            105.0,
            110.0,
            115.0,
            102.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        current_price=100.0,
        trend_direction="BULLISH",
        multi_timeframe_direction=(
            "BULLISH"
        ),
    )

    assert result["status"] == "READY"
    assert result["context"] == "BUY"
    assert result["price_zone"] == "DISCOUNT"
    assert result["context_score"] > 0


def test_detects_sell_context_in_premium():
    candles = build_candles(
        [
            100.0,
            105.0,
            110.0,
            115.0,
            102.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        current_price=115.0,
        trend_direction="BEARISH",
        multi_timeframe_direction=(
            "BEARISH"
        ),
    )

    assert result["context"] == "SELL"
    assert result["price_zone"] == "PREMIUM"
    assert result["context_score"] < 0


def test_detects_equilibrium():
    candles = build_candles(
        [
            90.0,
            95.0,
            100.0,
            105.0,
            110.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        current_price=100.0,
    )

    assert (
        result["price_zone"]
        == "EQUILIBRIUM"
    )

    assert (
        "price_near_equilibrium"
        in result["warnings"]
    )


def test_detects_near_range_low():
    candles = build_candles(
        [
            100.0,
            110.0,
            120.0,
            115.0,
            105.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        current_price=98.0,
    )

    assert result["near_range_low"] is True
    assert result["near_range_high"] is False


def test_detects_near_range_high():
    candles = build_candles(
        [
            100.0,
            110.0,
            120.0,
            115.0,
            105.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        current_price=122.0,
    )

    assert result["near_range_high"] is True
    assert result["near_range_low"] is False


def test_detects_trend_alignment():
    candles = build_candles(
        [
            100.0,
            102.0,
            104.0,
            106.0,
            108.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        trend_direction="BULLISH",
        multi_timeframe_direction=(
            "BULLISH"
        ),
    )

    assert result["trend_alignment"] is True
    assert (
        result["directional_conflict"]
        is False
    )


def test_blocks_directional_conflict():
    candles = build_candles(
        [
            100.0,
            102.0,
            104.0,
            106.0,
            108.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        trend_direction="BULLISH",
        multi_timeframe_direction=(
            "BEARISH"
        ),
    )

    assert result["context"] == "NEUTRAL"

    assert (
        "trend_timeframe_conflict"
        in result["blocking_reasons"]
    )


def test_uses_bullish_smart_money_bias():
    candles = build_candles(
        [
            100.0,
            102.0,
            104.0,
            106.0,
            108.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        current_price=104.0,
        smart_money_result={
            "structure": {
                "direction": "BULLISH",
            },
            "fvg": {
                "fvg": True,
                "direction": "BULLISH",
            },
            "order_block": {
                "order_block": True,
                "direction": "BULLISH",
            },
        },
    )

    assert (
        result["smart_money_bias"]
        == "BUY"
    )

    assert result["context_score"] > 0


def test_uses_bearish_smart_money_bias():
    candles = build_candles(
        [
            100.0,
            102.0,
            104.0,
            106.0,
            108.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        smart_money_result={
            "structure": {
                "direction": "BEARISH",
            },
            "fvg": {
                "fvg": True,
                "direction": "BEARISH",
            },
        },
    )

    assert (
        result["smart_money_bias"]
        == "SELL"
    )


def test_normalizes_direction_aliases():
    candles = build_candles(
        [
            100.0,
            102.0,
            104.0,
            106.0,
            108.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
        trend_direction="ALCISTA",
        multi_timeframe_direction="BUY",
    )

    assert (
        result["trend_direction"]
        == "BULLISH"
    )

    assert (
        result[
            "multi_timeframe_direction"
        ]
        == "BULLISH"
    )


def test_returns_insufficient_data():
    result = build_engine().analyze(
        candles=build_candles(
            [
                100.0,
                101.0,
            ]
        ),
    )

    assert (
        result["status"]
        == "INSUFFICIENT_DATA"
    )

    assert (
        "insufficient_candle_data"
        in result["blocking_reasons"]
    )


def test_rejects_price_outside_external_range():
    candles = build_candles(
        [
            100.0,
            102.0,
            104.0,
            106.0,
            108.0,
        ]
    )

    with pytest.raises(
        ValueError,
        match="current_price",
    ):
        build_engine().analyze(
            candles=candles,
            current_price=200.0,
        )


def test_rejects_invalid_candle_range():
    candles = build_candles(
        [
            100.0,
            102.0,
            104.0,
            106.0,
            108.0,
        ]
    )

    candles[-1].high = 90.0
    candles[-1].low = 100.0

    with pytest.raises(
        ValueError,
        match="candle.high",
    ):
        build_engine().analyze(
            candles=candles,
        )


def test_exposes_internal_and_external_ranges():
    candles = build_candles(
        [
            90.0,
            95.0,
            100.0,
            105.0,
            110.0,
            115.0,
            112.0,
            111.0,
        ]
    )

    result = build_engine().analyze(
        candles=candles,
    )

    assert "external_range" in result
    assert "internal_range" in result

    assert (
        result["external_range"][
            "range_size"
        ]
        >= result["internal_range"][
            "range_size"
        ]
    )
