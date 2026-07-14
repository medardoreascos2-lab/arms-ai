import pytest

from backend.pipeline.decision_stage import DecisionStage
from backend.pipeline.execution_stage import ExecutionStage
from backend.pipeline.indicator_stage import IndicatorStage
from backend.pipeline.intelligence_stage import IntelligenceStage
from backend.pipeline.market_stage import MarketStage
from backend.pipeline.reporting_stage import ReportingStage
from backend.pipeline.risk_stage import RiskStage
from backend.pipeline.smart_money_stage import SmartMoneyStage
from backend.pipeline.trade_plan_stage import TradePlanStage
from backend.services.data_collector import DataCollector


def build_context(tmp_path):
    collector = DataCollector(provider="SIMULATED")

    context = MarketStage(
        collector=collector,
        symbol="NASDAQ / NQ",
        timeframe="1m",
        candle_limit=100,
        max_candles=500,
    ).run(
        {
            "collector": collector,
        }
    )

    context = IndicatorStage().run(context)
    context = SmartMoneyStage().run(context)
    context = IntelligenceStage().run(context)
    context = RiskStage().run(context)
    context = DecisionStage().run(context)
    context = TradePlanStage().run(context)

    context = ExecutionStage(
        trade_log_path=str(tmp_path / "trade_plans.jsonl"),
        simulated_log_path=str(
            tmp_path / "simulated_trades.jsonl"
        ),
    ).run(context)

    return context


def test_reporting_stage_preserves_context(tmp_path):
    context = build_context(tmp_path)

    result = ReportingStage().run(context)

    assert result is context
    assert result["trade_plan"] is not None
    assert result["council_result"] is not None
    assert result["history_analyzer"] is not None


def test_reporting_stage_prints_main_sections(
    tmp_path,
    capsys,
):
    context = build_context(tmp_path)

    ReportingStage().run(context)

    output = capsys.readouterr().out

    expected_sections = [
        "------ CANDLE MANAGER ------",
        "------ EMA ENGINE ------",
        "------ MARKET STRUCTURE ------",
        "------ TRADING INTELLIGENCE ------",
        "------ DYNAMIC RISK ENGINE ------",
        "------ CONFLUENCE ENGINE ------",
        "------ REASONING RESULT ------",
        "------ PROBABILITY ENGINE ------",
        "------ DECISION COUNCIL ------",
        "------ TRADE PLAN ------",
        "------ TRADE LOGGER ------",
        "------ PLAN HISTORY ANALYZER ------",
    ]

    for section in expected_sections:
        assert section in output


def test_reporting_stage_requires_pipeline_results():
    stage = ReportingStage()

    with pytest.raises(
        KeyError,
        match="candle_manager",
    ):
        stage.run({})
