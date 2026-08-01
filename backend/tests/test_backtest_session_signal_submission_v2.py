import pytest

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

    def __init__(
        self,
        *,
        action=TradingActionV2.BUY,
    ) -> None:
        self.action = action

    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        return TradingDecisionV2(
            action=self.action,
            confidence=0.92,
            reason="BACKTEST SUBMISSION TEST",
            metadata={
                "stop_loss": 19950.0,
                "take_profit": 20100.0,
                "contracts": 2,
                "confluence_score": 0.90,
                "grade": "A+",
            },
        )


class FakeSignalSubmissionTargetV2(
    SignalSubmissionTargetV2,
):

    def __init__(self) -> None:
        self.calls = []

    def submit_signal(
        self,
        *,
        signal,
        order_type,
        risk_context=None,
        order_context=None,
    ):
        call = {
            "signal": signal,
            "order_type": order_type,
            "risk_context": risk_context,
            "order_context": order_context,
        }

        self.calls.append(call)

        return {
            "accepted": True,
            "active_position_id": "position-001",
            "signal": signal,
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


def build_session(
    *,
    target=None,
    action=TradingActionV2.BUY,
    risk_context=None,
    order_context=None,
) -> BacktestSessionV2:

    return BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(
            action=action,
        ),
        backtest_trade_plan_adapter_v2=(
            BacktestTradePlanAdapterV2()
        ),
        signal_generator_v2=(
            build_signal_generator()
        ),
        signal_submission_target_v2=target,
        signal_order_type="MARKET",
        signal_risk_context=risk_context,
        signal_order_context=order_context,
    )


def test_submits_generated_signal():

    target = FakeSignalSubmissionTargetV2()

    session = build_session(
        target=target,
    )

    processed = session.run()

    assert processed == 1
    assert len(session.signals) == 1
    assert len(target.calls) == 1
    assert len(session.submission_results) == 1

    call = target.calls[0]

    assert call["signal"] is session.signals[0]
    assert call["order_type"] == "MARKET"
    assert call["risk_context"] is None
    assert call["order_context"] is None

    result = session.submission_results[0]

    assert result["accepted"] is True
    assert (
        result["active_position_id"]
        == "position-001"
    )


def test_passes_optional_contexts():

    target = FakeSignalSubmissionTargetV2()

    risk_context = {
        "account_balance": 17000.0,
        "risk_percent": 0.5,
        "point_value": 2.0,
        "daily_pnl": 0.0,
        "total_drawdown": 0.0,
    }

    order_context = {
        "session": "NEW_YORK",
    }

    session = build_session(
        target=target,
        risk_context=risk_context,
        order_context=order_context,
    )

    session.run()

    call = target.calls[0]

    assert call["risk_context"] is risk_context
    assert call["order_context"] is order_context


def test_hold_does_not_submit_signal():

    target = FakeSignalSubmissionTargetV2()

    session = build_session(
        target=target,
        action=TradingActionV2.HOLD,
    )

    processed = session.run()

    assert processed == 1
    assert session.signals == []
    assert session.submission_results == []
    assert target.calls == []


def test_works_without_submission_target():

    session = build_session(
        target=None,
    )

    processed = session.run()

    assert processed == 1
    assert len(session.signals) == 1
    assert session.submission_results == []


def test_rejects_invalid_submission_target():

    with pytest.raises(
        TypeError,
        match="signal_submission_target_v2",
    ):
        build_session(
            target=object(),
        )


def test_rejects_empty_signal_order_type():

    with pytest.raises(
        ValueError,
        match="signal_order_type",
    ):
        BacktestSessionV2(
            backtest_runner_v2=FakeBacktestRunner(),
            strategy_runner_v2=FakeStrategyRunner(),
            backtest_trade_plan_adapter_v2=(
                BacktestTradePlanAdapterV2()
            ),
            signal_generator_v2=(
                build_signal_generator()
            ),
            signal_submission_target_v2=(
                FakeSignalSubmissionTargetV2()
            ),
            signal_order_type="   ",
        )


def test_clears_submission_results_between_runs():

    target = FakeSignalSubmissionTargetV2()

    session = build_session(
        target=target,
    )

    session.run()
    session.run()

    assert len(session.submission_results) == 1
    assert len(target.calls) == 2
