from backend.analytics.performance_analytics_v2 import (
    PerformanceAnalyticsV2,
)
from backend.analytics.trade_history_manager_v2 import (
    TradeHistoryManagerV2,
)
from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)
from backend.backtesting.backtest_trade_plan_adapter_v2 import (
    BacktestTradePlanAdapterV2,
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


class FakeBacktestRunner:

    def run(
        self,
        *,
        on_candle=None,
    ) -> int:

        if on_candle is not None:
            on_candle(
                {
                    "symbol": "NQ",
                    "timeframe": "5m",
                    "close": 20000.0,
                },
                {
                    "processed": True,
                },
            )

        return 1


class FakeStrategyRunner:

    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        return TradingDecisionV2(
            action=TradingActionV2.BUY,
            confidence=0.92,
            reason="BACKTEST E2E LONG",
            metadata={
                "stop_loss": 19950.0,
                "take_profit": 20100.0,
                "contracts": 2,
                "confluence_score": 0.90,
                "grade": "A+",
            },
        )


def build_lifecycle_service() -> TradeLifecycleServiceV2:

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


def test_backtest_opens_position_through_lifecycle_service():

    lifecycle = build_lifecycle_service()

    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(),
        backtest_trade_plan_adapter_v2=(
            BacktestTradePlanAdapterV2()
        ),
        signal_generator_v2=build_signal_generator(),
        signal_submission_target_v2=lifecycle,
        signal_order_type="MARKET",
    )

    processed = session.run()

    assert processed == 1
    assert len(session.decisions) == 1
    assert len(session.trade_plans) == 1
    assert len(session.signals) == 1
    assert len(session.submission_results) == 1

    result = session.submission_results[0]

    assert result["accepted"] is True
    assert result["execution"]["status"] == "FILLED"
    assert result["position"]["status"] == "OPEN"
    assert result["position"]["direction"] == "LONG"
    assert result["active_position_id"] is not None

    active_positions = lifecycle.get_active_positions()

    assert len(active_positions) == 1
    assert active_positions[0]["symbol"] == "NQ"
    assert active_positions[0]["direction"] == "LONG"
