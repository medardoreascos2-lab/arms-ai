from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.backtesting.backtest_batch_runner_v2 import (
    BacktestBatchRunnerV2,
)
from backend.backtesting.backtest_candidate_factory_v2 import (
    BacktestCandidateFactoryV2,
)
from backend.backtesting.backtest_comparison_report_v2 import (
    BacktestComparisonReportV2,
)
from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreV2,
)
from backend.backtesting.backtest_html_exporter_v2 import (
    BacktestHtmlExporterV2,
)
from backend.backtesting.backtest_json_exporter_v2 import (
    BacktestJsonExporterV2,
)
from backend.backtesting.backtest_optimizer_v2 import (
    BacktestOptimizerV2,
)
from backend.backtesting.backtest_pipeline_v2 import (
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
from backend.backtesting.parameter_grid_generator_v2 import (
    ParameterGridGeneratorV2,
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


class ReplayMarketDataBridgeV2:

    def publish(
        self,
        candle,
    ) -> dict[str, object]:

        return {
            "processed": True,
            "symbol": candle.symbol,
            "current_price": candle.close,
            "timestamp": candle.timestamp,
        }


class ParameterizedStrategyRunnerV2:

    def __init__(
        self,
        *,
        ema: int,
    ) -> None:

        self.ema = int(
            ema
        )

        self.calls = 0

    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        self.calls += 1

        if self.calls > 1:
            return TradingDecisionV2(
                action=TradingActionV2.HOLD,
                confidence=1.0,
                reason="NO NEW ENTRY",
            )

        if self.ema == 50:
            return TradingDecisionV2(
                action=TradingActionV2.BUY,
                confidence=0.95,
                reason="EMA50 LONG",
                metadata={
                    "stop_loss": 19950.0,
                    "take_profit": 20100.0,
                    "contracts": 2,
                    "confluence_score": 0.95,
                    "grade": "A+",
                },
            )

        return TradingDecisionV2(
            action=TradingActionV2.SELL,
            confidence=0.90,
            reason="EMA20 SHORT",
            metadata={
                "stop_loss": 20100.0,
                "take_profit": 19900.0,
                "contracts": 2,
                "confluence_score": 0.90,
                "grade": "A+",
            },
        )


def write_historical_csv(
    tmp_path,
):

    csv_path = (
        tmp_path
        / "optimizer_history.csv"
    )

    csv_path.write_text(
        (
            "timestamp,open,high,low,close,volume\n"
            "2026-01-01T09:30:00,19990,20010,19980,20000,1000\n"
            "2026-01-01T09:31:00,20000,20110,19995,20100,1200\n"
            "2026-01-01T09:32:00,20100,20105,20040,20050,900\n"
        ),
        encoding="utf-8",
    )

    return csv_path


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


def comparison_factory(
    batch_result,
):

    return (
        BacktestComparisonReportV2
        .from_batch_result(
            batch_result
        )
    )


def test_optimizer_executes_real_backtest_pipelines(
    tmp_path,
):

    csv_path = write_historical_csv(
        tmp_path
    )

    def pipeline_factory(
        parameters,
    ) -> BacktestPipelineV2:

        loader = CsvCandleLoaderV2(
            csv_path=csv_path,
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
                ReplayMarketDataBridgeV2()
            ),
        )

        lifecycle = build_lifecycle()

        session = BacktestSessionV2(
            backtest_runner_v2=runner,
            strategy_runner_v2=(
                ParameterizedStrategyRunnerV2(
                    ema=int(
                        parameters["ema"]
                    ),
                )
            ),
            backtest_trade_plan_adapter_v2=(
                BacktestTradePlanAdapterV2()
            ),
            signal_generator_v2=(
                build_signal_generator()
            ),
            signal_submission_target_v2=(
                lifecycle
            ),
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

        return BacktestPipelineV2(
            backtest_session_v2=session,
            json_exporter_v2=(
                BacktestJsonExporterV2()
            ),
            html_exporter_v2=(
                BacktestHtmlExporterV2()
            ),
        )

    parameter_sets = (
        ParameterGridGeneratorV2()
        .generate(
            {
                "ema": [
                    20,
                    50,
                ],
                "stop_loss": [
                    50,
                ],
                "take_profit": [
                    100,
                ],
            }
        )
    )

    candidates = (
        BacktestCandidateFactoryV2(
            pipeline_factory=pipeline_factory,
        )
        .build(
            parameter_sets=parameter_sets,
        )
    )

    optimizer = BacktestOptimizerV2(
        batch_runner=BacktestBatchRunnerV2(
            continue_on_error=False,
        ),
        comparison_report_factory=(
            comparison_factory
        ),
        scorer=BacktestCompositeScoreV2(
            minimum_trades=1,
        ),
    )

    result = optimizer.optimize(
        candidates=candidates,
        output_directory=(
            tmp_path
            / "optimization"
        ),
    )

    assert len(result.ranking) == 2

    best = result.best_strategy()

    assert best["name"] == (
        "EMA50_SL50_TP100"
    )

    assert best["parameters"] == {
        "ema": 50,
        "stop_loss": 50,
        "take_profit": 100,
    }

    assert best["net_pnl"] > 0

    losing_strategy = next(
        strategy
        for strategy in result.ranking
        if strategy["name"] != best["name"]
    )
    assert best["score"] > losing_strategy["score"]

    losing_strategy = result.ranking[1]

    assert losing_strategy["name"] == (
        "EMA20_SL50_TP100"
    )

    assert losing_strategy["net_pnl"] < 0

    assert (
        best["score"]
        > losing_strategy["score"]
    )

    assert (
        result.batch_result.total_runs
        == 2
    )

    assert (
        result.batch_result.successful_runs
        == 2
    )

    assert (
        result.batch_result.failed_runs
        == 0
    )

    for row in result.ranking:
        assert row["json_path"]
        assert row["html_path"]
