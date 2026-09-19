import pytest
from types import SimpleNamespace
from unittest.mock import Mock

from backend.accounts.account_config_manager_v2 import AccountConfigManagerV2
from backend.backtesting.backtest_execution_adapter_v2 import (
    BacktestExecutionAdapterV2,
)

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
        stop_loss=19950.0,
    ) -> None:
        self.action = action
        self.stop_loss = stop_loss

    def run(
        self,
        context,
    ) -> TradingDecisionV2:

        return TradingDecisionV2(
            action=self.action,
            confidence=0.92,
            reason="BACKTEST SUBMISSION TEST",
            metadata={
                "stop_loss": self.stop_loss,
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
    executor=None,
    stop_loss=19950.0,
) -> BacktestSessionV2:

    return BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(
            action=action,
            stop_loss=stop_loss,
        ),
        trade_executor_v2=executor,
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


@pytest.fixture
def independent_executor(monkeypatch, tmp_path):
    """Observe the real adapter and simulator, including their trade output."""
    account_path = tmp_path / "accounts.json"
    account_path.write_text('{"active_account":"TOPSTEP_150K"}\n', encoding="utf-8")
    monkeypatch.setattr(AccountConfigManagerV2, "DEFAULT_CONFIG_PATH", account_path)
    executor = BacktestExecutionAdapterV2()
    executor.execute = Mock(wraps=executor.execute)
    executor.simulator.simulate = Mock(wraps=executor.simulator.simulate)
    return executor


def configure_future_candles(session):
    session.future_candles = [
        SimpleNamespace(high=20100.0, low=20000.0, close=20100.0),
    ]


def build_execution_session(**kwargs):
    # This synthetic 30-point stop fits the canonical account's existing budget.
    # Exercise real risk sizing without changing its limits or approval result.
    return build_session(stop_loss=19970.0, **kwargs)


@pytest.mark.parametrize(
    "submission_result",
    [
        {"accepted": False, "reason": "risk_rejected"},
        {},
        {"accepted": None},
        {"accepted": "false"},
        {"accepted": 1},
        None,
        True,
    ],
)
def test_unaccepted_submission_never_calls_independent_executor(
    independent_executor, submission_result,
):
    target = FakeSignalSubmissionTargetV2()
    target.submit_signal = Mock(return_value=submission_result)
    session = build_execution_session(target=target, executor=independent_executor)
    configure_future_candles(session)
    session.risk_pipeline.evaluate = Mock(wraps=session.risk_pipeline.evaluate)

    assert session.run() == 1

    target.submit_signal.assert_called_once()
    assert target.submit_signal.call_args.kwargs["signal"] is session.signals[0]
    assert session.submission_results == [submission_result]
    session.risk_pipeline.evaluate.assert_not_called()
    independent_executor.execute.assert_not_called()
    independent_executor.simulator.simulate.assert_not_called()
    assert session.simulated_trades == []
    assert session.active_position_id is None


def test_accepted_submission_preserves_independent_simulation_and_position(
    independent_executor,
):
    target = FakeSignalSubmissionTargetV2()
    session = build_execution_session(target=target, executor=independent_executor)
    configure_future_candles(session)

    assert session.run() == 1

    assert len(target.calls) == 1
    independent_executor.execute.assert_called_once()
    independent_executor.simulator.simulate.assert_called_once()
    assert session.active_position_id == "position-001"
    assert len(session.simulated_trades) == 1
    trade = session.simulated_trades[0]
    assert trade.status == "WIN"
    assert trade.pnl > 0
    assert session.submission_results[0]["accepted"] is True
    assert session.submission_results[1] is trade
    assert len(session.submission_results) == 2
    assert independent_executor.simulator.simulate.call_args.kwargs["candles"] is session.future_candles


def test_standalone_executor_preserves_simulated_trade(independent_executor):
    session = build_execution_session(executor=independent_executor)
    configure_future_candles(session)

    assert session.run() == 1

    independent_executor.execute.assert_called_once()
    independent_executor.simulator.simulate.assert_called_once()
    assert session.signal_submission_target_v2 is None
    assert len(session.simulated_trades) == 1
    assert session.simulated_trades[0].status == "WIN"
    assert session.submission_results == session.simulated_trades


def test_hold_with_both_paths_has_no_execution(independent_executor):
    target = FakeSignalSubmissionTargetV2()
    session = build_execution_session(
        target=target, executor=independent_executor, action=TradingActionV2.HOLD,
    )
    configure_future_candles(session)

    assert session.run() == 1

    assert target.calls == []
    independent_executor.execute.assert_not_called()
    independent_executor.simulator.simulate.assert_not_called()
    assert session.signals == []
    assert session.submission_results == []
    assert session.simulated_trades == []


def test_configured_target_without_signal_pipeline_fails_closed(
    independent_executor,
):
    target = FakeSignalSubmissionTargetV2()
    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=FakeStrategyRunner(),
        signal_submission_target_v2=target,
        trade_executor_v2=independent_executor,
    )

    assert session.run() == 1

    assert target.calls == []
    independent_executor.execute.assert_not_called()
    independent_executor.simulator.simulate.assert_not_called()
    assert session.submission_results == []
    assert session.simulated_trades == []


def test_accepted_submission_does_not_bypass_executor_risk(independent_executor):
    target = FakeSignalSubmissionTargetV2()
    session = build_execution_session(target=target, executor=independent_executor)
    session.risk_pipeline.evaluate = Mock(
        return_value=SimpleNamespace(allowed=False),
    )

    assert session.run() == 1

    assert len(target.calls) == 1
    assert session.submission_results[0]["accepted"] is True
    session.risk_pipeline.evaluate.assert_called_once()
    independent_executor.execute.assert_not_called()
    independent_executor.simulator.simulate.assert_not_called()
    assert session.simulated_trades == []


def test_acceptance_is_not_reused_for_a_later_rejected_decision(
    independent_executor,
):
    accepted = {"accepted": True}
    rejected = {"accepted": False, "reason": "risk_rejected"}
    target = FakeSignalSubmissionTargetV2()
    target.submit_signal = Mock(side_effect=[accepted, rejected])
    session = build_execution_session(target=target, executor=independent_executor)
    configure_future_candles(session)
    single_candle_run = session.backtest_runner_v2.run

    def run_two_candles(*, on_candle):
        return single_candle_run(on_candle=on_candle) + single_candle_run(
            on_candle=on_candle,
        )

    session.backtest_runner_v2.run = run_two_candles

    assert session.run() == 2

    assert target.submit_signal.call_count == 2
    independent_executor.execute.assert_called_once()
    independent_executor.simulator.simulate.assert_called_once()
    assert len(session.simulated_trades) == 1
    assert session.submission_results == [
        accepted, session.simulated_trades[0], rejected,
    ]
