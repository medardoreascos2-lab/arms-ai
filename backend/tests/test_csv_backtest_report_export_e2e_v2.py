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
from backend.execution.execution_risk_gate_v1 import (
    ExecutionRiskGateV1,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)
from backend.execution.position_manager_v2 import (
    PositionManagerV2,
)
from backend.execution.position_sizing_engine_v2 import (
    PositionSizingEngineV2,
)
from backend.execution.risk_manager_v2 import (
    RiskManagerV2,
)
from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)
from backend.accounts.profiles.takeprofit_profiles import (
    TakeProfitTraderProfiles,
)

TEST_ACCOUNT = (
    TakeProfitTraderProfiles.account_150k()
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
                reason="LONG ENTRY",
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
                reason="SHORT ENTRY",
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


def write_csv(tmp_path):

    path = tmp_path / "nq_history.csv"

    path.write_text(
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

    return path


def build_lifecycle() -> TradeLifecycleServiceV2:

    position_sizing_engine = (
        PositionSizingEngineV2()
    )

    risk_manager_v2 = RiskManagerV2(
        position_sizing_engine=(
            position_sizing_engine
        ),
        maximum_daily_loss=(
            TEST_ACCOUNT.daily_loss_limit
        ),
        maximum_total_drawdown=(
            TEST_ACCOUNT.max_drawdown
        ),
        maximum_contracts=(
            TEST_ACCOUNT.max_contracts
        ),
        maximum_open_positions=1,
    )

    return TradeLifecycleServiceV2(
        risk_manager_v2=(
            risk_manager_v2
        ),
        execution_manager=ExecutionManagerV2(
            execution_mode="PAPER",
            maximum_contracts=TEST_ACCOUNT.max_contracts,
        ),
        paper_execution_engine=PaperExecutionEngineV2(
            fill_market_orders_immediately=True,
            slippage_points=0.25,
        ),
        position_manager=PositionManagerV2(
            point_value=float(
                InstrumentProfileEngine()
                .get_profile(symbol="MNQ")["point_value"]
            ),
        ),
        trade_history_manager=TradeHistoryManagerV2(),
        performance_analytics=PerformanceAnalyticsV2(
            risk_free_rate=0.0,
            trading_days_per_year=252,
        ),
        starting_balance=17000.0,
        execution_risk_gate_v1=(
            ExecutionRiskGateV1()
        ),
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


def test_csv_backtest_builds_and_exports_report(
    tmp_path,
):

    loader = CsvCandleLoaderV2(
        csv_path=write_csv(tmp_path),
        symbol="MNQ",
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
        signal_risk_context={
            "account_balance": float(TEST_ACCOUNT.account_size),
            "risk_percent": float(TEST_ACCOUNT.risk_percent),
            "point_value": float(InstrumentProfileEngine().get_profile(symbol="MNQ")["point_value"]),
            "daily_pnl": 0.0,
            "total_drawdown": 0.0,
        },
        signal_order_context={
            "market_is_open": True,
        },
    )

    processed = session.run()

    report = session.build_report(
        candles_processed=processed,
    )

    reports_dir = tmp_path / "reports"

    json_path = (
        reports_dir
        / "backtest.json"
    )

    html_path = (
        reports_dir
        / "backtest.html"
    )

    json_result = BacktestJsonExporterV2().export(
        report=report,
        output_path=json_path,
    )

    html_result = BacktestHtmlExporterV2().export(
        report=report,
        output_path=html_path,
    )

    assert json_result == json_path
    assert html_result == html_path

    assert json_path.exists()
    assert html_path.exists()

    payload = json.loads(
        json_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["summary"] == {
        "candles_processed": 5,
        "decisions": 5,
        "trade_plans": 2,
        "signals": 2,
        "submissions": 2,
        "position_updates": 2,
        "closed_trades": 2,
        "active_positions": 0,
    }

    assert payload[
        "performance_metrics"
    ]["total_trades"] == 2

    assert payload[
        "performance_metrics"
    ]["wins"] == 1

    assert payload[
        "performance_metrics"
    ]["losses"] == 1

    assert len(
        payload["trade_history"]
    ) == 2

    html = html_path.read_text(
        encoding="utf-8",
    )

    assert "Backtest Report" in html
    assert "candles_processed" in html
    assert "trade_history" in html
    assert "performance_metrics" in html

    assert lifecycle.get_active_positions() == []
    assert replay_engine.has_next() is False
