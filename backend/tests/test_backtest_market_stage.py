from datetime import datetime, timedelta

import pytest

from backend.models.candle import Candle
from backend.pipeline.backtest_market_stage import BacktestMarketStage


def build_candles(total: int) -> list[Candle]:
    base_time = datetime(2026, 1, 1, 9, 30)
    candles = []

    for index in range(total):
        price = 21600.0 + index

        candles.append(
            Candle(
                symbol="NASDAQ / NQ",
                timeframe="1m",
                open=price,
                high=price + 2.0,
                low=price - 1.0,
                close=price + 1.0,
                volume=1000 + index,
                timestamp=base_time + timedelta(minutes=index),
            )
        )

    return candles


def test_backtest_market_stage_builds_market_context():
    candles = build_candles(60)

    context = BacktestMarketStage(
        max_candles=500,
    ).run(
        {
            "backtest_candles": candles,
        }
    )

    assert context["candles"] == candles
    assert context["latest_candle"] == candles[-1]
    assert context["current_price"] == candles[-1].close
    assert context["current_volume"] == candles[-1].volume

    assert len(
        context["candle_manager"].get_close_prices()
    ) == 60

    assert context["market"] is not None
    assert context["feed"] is not None


def test_backtest_market_stage_preserves_context():
    candles = build_candles(60)

    context = BacktestMarketStage().run(
        {
            "backtest_candles": candles,
            "session_allowed": True,
        }
    )

    assert context["session_allowed"] is True


def test_backtest_market_stage_requires_candles():
    with pytest.raises(
        KeyError,
        match="backtest_candles",
    ):
        BacktestMarketStage().run({})


def test_backtest_market_stage_rejects_empty_candles():
    with pytest.raises(
        ValueError,
        match="vacía",
    ):
        BacktestMarketStage().run(
            {
                "backtest_candles": [],
            }
        )
