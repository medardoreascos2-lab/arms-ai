from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)
from backend.backtesting.backtest_trade_plan_adapter_v2 import (
    BacktestTradePlanAdapterV2,
)
from backend.services.signal_submission_target_v2 import (
    SignalSubmissionTargetV2,
)
from backend.signals.signal_generator_v2 import (
    SignalGeneratorV2,
)
from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class FakeBacktestRunner:

    def run(self, *, on_candle=None) -> int:

        candles = [
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20000.0,
            },
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20020.0,
            },
            {
                "symbol": "NQ",
                "timeframe": "5m",
                "close": 20040.0,
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


class FakeStrategyRunner:

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
                reason="ENTRY",
                metadata={
                    "stop_loss": 19950.0,
                    "take_profit": 20100.0,
                    "contracts": 2,
                    "confluence_score": 0.90,
                    "grade": "A+",
                },
            )

        return TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=1.0,
            reason="HOLD",
        )


class FakeLifecycle(
    SignalSubmissionTargetV2,
):

    def __init__(self) -> None:
        self.submit_calls = []
        self.update_calls = []

    def submit_signal(
        self,
        *,
        signal,
        order_type,
        risk_context=None,
        order_context=None,
    ):
        self.submit_calls.append(
            {
                "signal": signal,
                "order_type": order_type,
                "risk_context": risk_context,
                "order_context": order_context,
            }
        )

        return {
            "accepted": True,
            "active_position_id": "POS-1",
        }

    def update_position(
        self,
        *,
        position_id,
        current_price,
    ):
        self.update_calls.append(
            {
                "position_id": position_id,
                "current_price": current_price,
            }
        )

        return {
            "updated": True,
            "position": {
                "position_id": position_id,
                "status": "OPEN",
                "current_price": current_price,
            },
        }


def build_signal_generator() -> SignalGeneratorV2:

    return SignalGeneratorV2(
        minimum_probability=0.80,
        minimum_confluence_score=0.80,
        allowed_grades={
            "A+",
            "A",
        },
    )


def test_backtest_updates_open_position_on_later_candles():

    lifecycle = FakeLifecycle()

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

    assert processed == 3
    assert len(lifecycle.submit_calls) == 1

    assert lifecycle.update_calls == [
        {
            "position_id": "POS-1",
            "current_price": 20020.0,
        },
        {
            "position_id": "POS-1",
            "current_price": 20040.0,
        },
    ]
