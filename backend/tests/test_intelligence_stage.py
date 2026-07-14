import pytest

from backend.pipeline.indicator_stage import IndicatorStage
from backend.pipeline.intelligence_stage import IntelligenceStage
from backend.pipeline.market_stage import MarketStage
from backend.pipeline.smart_money_stage import SmartMoneyStage
from backend.services.data_collector import DataCollector


def build_context():
    collector = DataCollector(provider="SIMULATED")

    context = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=100,
        max_candles=500,
    ).run({})

    context = IndicatorStage(
        ema_period=50,
        rsi_period=14,
        atr_period=14,
    ).run(context)

    context = SmartMoneyStage(
        liquidity_tolerance=1.0,
    ).run(context)

    return context


def test_intelligence_stage_adds_trend_intelligence_and_decision():
    context = build_context()

    stage = IntelligenceStage()

    result = stage.run(context)

    assert "trend" in result
    assert "intelligence" in result
    assert "decision" in result

    assert result["trend"].trend is not None
    assert result["intelligence"].recommendation is not None
    assert result["intelligence"].confidence is not None
    assert result["decision"].decision is not None


def test_intelligence_stage_preserves_existing_context():
    context = build_context()
    context["session_allowed"] = True

    result = IntelligenceStage().run(context)

    assert result["session_allowed"] is True
    assert result["current_price"] == result["latest_candle"].close
    assert result["market_structure"].structure is not None


def test_intelligence_stage_requires_pipeline_dependencies():
    stage = IntelligenceStage()

    with pytest.raises(
        KeyError,
        match="current_price",
    ):
        stage.run({})
