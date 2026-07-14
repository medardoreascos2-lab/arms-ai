import pytest

from backend.pipeline.decision_stage import DecisionStage
from backend.pipeline.execution_stage import ExecutionStage
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
    context = TradePlanStage().run(context)

    context["collector"] = collector

    return context


def test_execution_stage_logs_and_analyzes_trade_plan(tmp_path):
    context = build_context()

    trade_log_path = tmp_path / "trade_plans.jsonl"
    simulated_log_path = tmp_path / "simulated_trades.jsonl"

    stage = ExecutionStage(
        trade_log_path=str(trade_log_path),
        simulated_log_path=str(simulated_log_path),
        point_value=2.0,
    )

    result = stage.run(context)

    assert trade_log_path.exists()
    assert "history_analyzer" in result
    assert "simulated_trade" in result

    assert result["history_analyzer"].total_plans == 1


def test_execution_stage_preserves_existing_context(tmp_path):
    context = build_context()
    context["session_allowed"] = True

    result = ExecutionStage(
        trade_log_path=str(tmp_path / "plans.jsonl"),
        simulated_log_path=str(tmp_path / "trades.jsonl"),
    ).run(context)

    assert result["session_allowed"] is True
    assert result["trade_plan"] is not None


def test_execution_stage_requires_pipeline_dependencies():
    stage = ExecutionStage()

    with pytest.raises(
        KeyError,
        match="trade_plan",
    ):
        stage.run({})
