from __future__ import annotations

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
    BacktestPipelineV2,
)

from backend.backtesting.backtest_runner_v2 import (
    BacktestRunnerV2,
)

from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)

from backend.backtesting.backtest_execution_adapter_v2 import (
    BacktestExecutionAdapterV2,
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

from backend.backtesting.replay_market_data_bridge_v2 import (
    ReplayMarketDataBridgeV2,
)


from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
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

from backend.strategies.parameterized_strategy_runner_v2 import (
    ParameterizedStrategyRunnerV2,
)


def build_lifecycle() -> TradeLifecycleServiceV2:

    from backend.accounts.account_config_manager_v2 import (
        AccountConfigManagerV2,
    )

    account = (
        AccountConfigManagerV2()
        .get_active_account()
    )

    instrument_profiles = (
        InstrumentProfileEngine()
    )

    def resolve_contract_limit(
        symbol: str,
    ) -> int:
        profile = (
            instrument_profiles
            .get_profile(symbol=symbol)
        )

        return account.get_contract_limit(
            profile["contract_class"]
        )

    runtime_contract_limit = min(
        account.get_contract_limit("MINI"),
        account.get_contract_limit("MICRO"),
    )

    return TradeLifecycleServiceV2(
        execution_manager=(
            ExecutionManagerV2(
                execution_mode="PAPER",
                maximum_contracts=(
                    runtime_contract_limit
                ),
                contract_limit_resolver=(
                    resolve_contract_limit
                ),
            )
        ),
        paper_execution_engine=(
            PaperExecutionEngineV2(
                fill_market_orders_immediately=True,
                slippage_points=0.25,
            )
        ),
        position_manager=(
            PositionManagerV2(
                point_value=float(
                    InstrumentProfileEngine()
                    .get_profile(
                        symbol="NQ"
                    )["point_value"]
                ),
            )
        ),
        trade_history_manager=(
            TradeHistoryManagerV2()
        ),
        performance_analytics=(
            PerformanceAnalyticsV2(
                risk_free_rate=0.0,
                trading_days_per_year=252,
            )
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


def build_strategy_backtest_pipeline(
    parameters,
    *,
    csv_path,
) -> BacktestPipelineV2:

    loader = CsvCandleLoaderV2(
        csv_path=csv_path,
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
                )
            )
        ),

        trade_executor_v2=(
            BacktestExecutionAdapterV2()
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
