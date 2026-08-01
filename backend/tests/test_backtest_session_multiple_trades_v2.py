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

        candles = [
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20000.0,
            },
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20100.0,
            },
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20050.0,
            },
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20100.0,
            },
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20020.0,
            },
        ]

        for candle in candles:
            if on_candle is not None:
                on_candle(
                    candle,
                    {
                        "processed": True,
                    },
                )

        return len(candles)


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
                reason="FIRST LONG ENTRY",
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
                reason="SECOND SHORT ENTRY",
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
            reason="NO NEW ENTRY",
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


def test_backtest_executes_multiple_complete_trade_cycles():

    lifecycle = build_lifecycle_service()

    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
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

    processed = session.run()

    assert processed == 5

    assert len(session.decisions) == 5
    assert len(session.trade_plans) == 2
    assert len(session.signals) == 2
    assert len(session.submission_results) == 2
    assert len(session.position_update_results) == 2

    assert all(
        result["accepted"] is True
        for result in session.submission_results
    )

    history = lifecycle.get_trade_history()

    assert len(history) == 2

    first_trade = history[0]
    second_trade = history[1]

    assert first_trade["direction"] == "LONG"
    assert first_trade["close_reason"] == "TAKE_PROFIT"
    assert first_trade["result"] == "WIN"
    assert first_trade["realized_pnl"] > 0

    assert second_trade["direction"] == "SHORT"
    assert second_trade["close_reason"] == "STOP_LOSS"
    assert second_trade["result"] == "LOSS"
    assert second_trade["realized_pnl"] < 0

    metrics = lifecycle.get_performance_metrics()

    assert metrics["total_trades"] == 2
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["win_rate"] == 0.5
    assert len(metrics["equity_curve"]) == 3

    assert lifecycle.get_active_positions() == []
    assert session.active_position_id is None
