import json

from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.backtesting.backtest_html_exporter_v2 import (
    BacktestHtmlExporterV2,
)
from backend.backtesting.backtest_json_exporter_v2 import (
    BacktestJsonExporterV2,
)
from backend.backtesting.backtest_pipeline_v2 import (
    BacktestPipelineResultV2,
    BacktestPipelineV2,
)
from backend.backtesting.backtest_runner_v2 import (
    BacktestRunnerV2,
)
from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)
from backend.backtesting.backtest_trade_plan_adapter_v2 import (
    BacktestTradePlanAdapterV2,
)
from backend.backtesting.csv_candle_loader_v2 import (
    CsvCandleLoaderV2,
)
from backend.backtesting.replay_engine_v2 import (
    ReplayEngineV2,
)
from backend.execution.execution_manager_v2 import (
    ExecutionManagerV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.services.trade_lifecycle_service_v2 import (
    TradeLifecycleServiceV2,
)
from backend.signals.signal_generator_v2 import (
    SignalGeneratorV2,
)
from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class FakeReplayMarketDataBridgeV2:

    def publish(self, candle):

        return {
            "processed": True,
            "symbol": candle.symbol,
            "current_price": candle.close,
            "timestamp": candle.timestamp,
        }


class MultipleTradesStrategyRunner:

    def __init__(self) -> None:
        self.calls = 0

    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        self.calls += 1

        if self.calls == 1:
            return TradingDecisionV2(
                action=TradingActionV2.BUY,
                confidence=0.95,
                reason="PIPELINE LONG ENTRY",
                metadata={
                    "stop_loss": 19950.0,
                    "take_profit": 20100.0,
                    "contracts": 2,
                    "confluence_score": 0.92,
                    "grade": "A+",
                },
            )

        if self.calls == 3:
            return TradingDecisionV2(
                action=TradingActionV2.SELL,
                confidence=0.93,
                reason="PIPELINE SHORT ENTRY",
                metadata={
                    "stop_loss": 20100.0,
                    "take_profit": 19950.0,
                    "contracts": 2,
                    "confluence_score": 0.90,
                    "grade": "A+",
                },
            )

        return TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=1.0,
            reason="NO ENTRY",
        )


def write_historical_csv(tmp_path):

    csv_path = tmp_path / "nq_pipeline_history.csv"

    csv_path.write_text(
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:30:00,19990,20010,19980,20000,1000\n"
            "2026-01-01T09:31:00,20000,20110,19995,20100,1200\n"
            "2026-01-01T09:32:00,20080,20090,20040,20050,1100\n"
            "2026-01-01T09:33:00,20050,20110,20040,20100,1300\n"
            "2026-01-01T09:34:00,20100,20105,20010,20020,900\n"
        ),
        encoding="utf-8",
    )

    return csv_path


def build_lifecycle() -> TradeLifecycleServiceV2:

    return TradeLifecycleServiceV2(
        execution_manager=ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=20,
        ),
        paper_execution_engine=PaperExecutionEngineV2(
            fill_market_orders_immediately=True,
            slippage_points=0.25,
        ),
        position_manager=PositionManagerV2(
            point_value=2.0,
        ),
        trade_history_manager=TradeHistoryManagerV2(),
        performance_analytics=PerformanceAnalyticsV2(
            risk_free_rate=0.0,
            trading_days_per_year=252,
        ),
        starting_balance=17000.0,
    )


def build_signal_generator() -> SignalGeneratorV2:

    return SignalGeneratorV2(
        minimum_probability=0.80,
        minimum_confluence_score=0.80,
        allowed_grades={
            "A+",
            "A",
        },
    )


def test_real_pipeline_runs_csv_backtest_and_exports_reports(
    tmp_path,
):

    loader = CsvCandleLoaderV2(
        csv_path=write_historical_csv(tmp_path),
        symbol="NQ",
        timeframe="1m",
    )

    replay_engine = ReplayEngineV2()

    replay_engine.load(
        loader.load()
    )

    runner = BacktestRunnerV2(
        replay_engine_v2=replay_engine,
        replay_market_data_bridge_v2=(
            FakeReplayMarketDataBridgeV2()
        ),
    )

    lifecycle = build_lifecycle()

    session = BacktestSessionV2(
        backtest_runner_v2=runner,
        strategy_runner_v2=(
            MultipleTradesStrategyRunner()
        ),
        backtest_trade_plan_adapter_v2=(
            BacktestTradePlanAdapterV2()
        ),
        signal_generator_v2=build_signal_generator(),
        signal_submission_target_v2=lifecycle,
        signal_order_type="MARKET",
    )

    pipeline = BacktestPipelineV2(
        backtest_session_v2=session,
        json_exporter_v2=(
            BacktestJsonExporterV2()
        ),
        html_exporter_v2=(
            BacktestHtmlExporterV2()
        ),
    )

    output_directory = (
        tmp_path
        / "reports"
    )

    result = pipeline.run(
        output_directory=output_directory,
        json_filename="nq_backtest.json",
        html_filename="nq_backtest.html",
    )

    assert isinstance(
        result,
        BacktestPipelineResultV2,
    )

    assert result.candles_processed == 5

    assert result.json_path == (
        output_directory
        / "nq_backtest.json"
    )

    assert result.html_path == (
        output_directory
        / "nq_backtest.html"
    )

    assert result.json_path.exists()
    assert result.html_path.exists()

    assert result.report.summary() == {
        "candles_processed": 5,
        "decisions": 5,
        "trade_plans": 2,
        "signals": 2,
        "submissions": 2,
        "position_updates": 2,
        "closed_trades": 2,
        "active_positions": 0,
    }

    metrics = result.report.performance_metrics

    assert metrics["total_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["win_rate"] == 0.5

    assert len(
        result.report.trade_history
    ) == 2

    assert (
        result.report.trade_history[0]["result"]
        == "WIN"
    )

    assert (
        result.report.trade_history[1]["result"]
        == "LOSS"
    )

    json_payload = json.loads(
        result.json_path.read_text(
            encoding="utf-8",
        )
    )

    assert (
        json_payload["summary"]
        == result.report.summary()
    )

    assert (
        json_payload["performance_metrics"][
            "total_trades"
        ]
        == 2
    )

    html = result.html_path.read_text(
        encoding="utf-8",
    )

    assert "Backtest Report" in html
    assert "candles_processed" in html
    assert "performance_metrics" in html
    assert "trade_history" in html

    assert lifecycle.get_active_positions() == []
    assert replay_engine.has_next() is False
