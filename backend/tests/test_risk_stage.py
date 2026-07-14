import pytest

from backend.pipeline.indicator_stage import IndicatorStage
from backend.pipeline.intelligence_stage import IntelligenceStage
from backend.pipeline.market_stage import MarketStage
from backend.pipeline.risk_stage import RiskStage
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

    context = IntelligenceStage().run(context)

    return context


def test_risk_stage_adds_risk_components_to_context():
    context = build_context()

    stage = RiskStage(
        account_balance=17000,
        risk_percent=0.5,
        stop_atr_multiplier=1.5,
        reward_risk_ratio=2.0,
        point_value=2.0,
    )

    result = stage.run(context)

    assert "risk_manager" in result
    assert "dynamic_risk" in result
    assert "trade_levels" in result
    assert "validator" in result

    assert result["dynamic_risk"].risk_amount > 0
    assert result["dynamic_risk"].stop_distance > 0
    assert result["dynamic_risk"].take_profit_distance > 0
    assert result["dynamic_risk"].contracts >= 0
    assert result["validator"].is_valid is not None


def test_risk_stage_preserves_existing_context():
    context = build_context()
    context["session_allowed"] = True

    result = RiskStage().run(context)

    assert result["session_allowed"] is True
    assert result["current_price"] == result["latest_candle"].close
    assert result["decision"].decision is not None


def test_risk_stage_requires_pipeline_dependencies():
    stage = RiskStage()

    with pytest.raises(
        KeyError,
        match="current_price",
    ):
        stage.run({})
