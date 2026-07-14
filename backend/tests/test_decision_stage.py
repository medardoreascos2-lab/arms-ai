import pytest

from backend.pipeline.decision_stage import DecisionStage
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

    context = RiskStage(
        account_balance=17000,
        risk_percent=0.5,
        stop_atr_multiplier=1.5,
        reward_risk_ratio=2.0,
        point_value=2.0,
    ).run(context)

    return context


def test_decision_stage_adds_all_decision_results():
    context = build_context()

    stage = DecisionStage(
        reward_risk_ratio=2.0,
    )

    result = stage.run(context)

    assert "confluence_result" in result
    assert "reasoning_result" in result
    assert "probability_result" in result
    assert "council_result" in result

    assert result["confluence_result"].score >= 0
    assert result["reasoning_result"].quality_score >= 0
    assert result["probability_result"].probability >= 0
    assert result["council_result"].action is not None


def test_decision_stage_preserves_existing_context():
    context = build_context()
    context["session_allowed"] = True

    result = DecisionStage().run(context)

    assert result["session_allowed"] is True
    assert result["validator"].is_valid is not None
    assert result["trade_levels"].entry_price is not None


def test_decision_stage_requires_pipeline_dependencies():
    stage = DecisionStage()

    with pytest.raises(
        KeyError,
        match="trend",
    ):
        stage.run({})
