import pytest

from backend.pipeline.indicator_stage import IndicatorStage
from backend.pipeline.market_stage import MarketStage
from backend.services.data_collector import DataCollector


def test_indicator_stage_adds_ema_rsi_and_atr_to_context():
    collector = DataCollector(provider="SIMULATED")

    market_stage = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=100,
        max_candles=500,
    )

    context = market_stage.run({})

    indicator_stage = IndicatorStage(
        ema_period=50,
        rsi_period=14,
        atr_period=14,
    )

    result = indicator_stage.run(context)

    assert "close_prices" in result
    assert "ema" in result
    assert "rsi" in result
    assert "atr" in result

    assert len(result["close_prices"]) == 100
    assert result["ema"].ema is not None
    assert result["rsi"].rsi is not None
    assert result["atr"].atr is not None


def test_indicator_stage_preserves_market_context():
    collector = DataCollector(provider="SIMULATED")

    market_stage = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=60,
        max_candles=100,
    )

    context = market_stage.run(
        {"session_allowed": True}
    )

    indicator_stage = IndicatorStage()

    result = indicator_stage.run(context)

    assert result["session_allowed"] is True
    assert result["latest_candle"] is not None
    assert result["current_price"] == result["latest_candle"].close
    assert len(result["close_prices"]) == 60


def test_indicator_stage_requires_market_data():
    indicator_stage = IndicatorStage()

    with pytest.raises(
        KeyError,
        match="candle_manager",
    ):
        indicator_stage.run({})


def test_indicator_stage_rejects_insufficient_candles():
    collector = DataCollector(provider="SIMULATED")

    market_stage = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=30,
        max_candles=100,
    )

    context = market_stage.run({})

    indicator_stage = IndicatorStage(
        ema_period=50,
    )

    with pytest.raises(
        ValueError,
        match="al menos 50 precios",
    ):
        indicator_stage.run(context)
