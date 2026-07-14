import pytest

from backend.pipeline.decision_stage import DecisionStage
from backend.pipeline.indicator_stage import IndicatorStage
from backend.pipeline.intelligence_stage import IntelligenceStage
from backend.pipeline.market_stage import MarketStage
from backend.pipeline.risk_stage import RiskStage
from backend.pipeline.smart_money_stage import SmartMoneyStage
from backend.pipeline.trade_plan_stage import TradePlanStage
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

    context = IndicatorStage().run(context)
    context = SmartMoneyStage().run(context)
    context = IntelligenceStage().run(context)
    context = RiskStage().run(context)
    context = DecisionStage().run(context)

    return context


def test_trade_plan_stage_adds_trade_plan_to_context():
    context = build_context()

    result = TradePlanStage().run(context)

    assert "trade_plan" in result
    assert result["trade_plan"].decision is not None
    assert result["trade_plan"].confidence is not None
    assert result["trade_plan"].authorized is not None


def test_trade_plan_stage_builds_safe_blocked_plan():
    context = build_context()

    result = TradePlanStage().run(context)
    trade_plan = result["trade_plan"]

    if not context["council_result"].approved:
        assert trade_plan.decision == "NO_TRADE"
        assert trade_plan.authorized is False
        assert trade_plan.contracts == 0
        assert trade_plan.risk_amount == 0.0
        assert trade_plan.entry_price is None
        assert trade_plan.stop_loss is None
        assert trade_plan.take_profit is None


def test_trade_plan_stage_preserves_existing_context():
    context = build_context()
    context["session_allowed"] = True

    result = TradePlanStage().run(context)

    assert result["session_allowed"] is True
    assert result["council_result"].action is not None


def test_trade_plan_stage_requires_pipeline_dependencies():
    stage = TradePlanStage()

    with pytest.raises(
        KeyError,
        match="latest_candle",
    ):
        stage.run({})
