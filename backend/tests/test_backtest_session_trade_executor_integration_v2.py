import pytest

from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class FakeBacktestRunner:

    def __init__(
        self,
        *,
        candle=None,
    ):
        self.candle = candle or {
            "symbol": "NQ",
            "close": 20000.0,
        }

    def run(self, *, on_candle=None):

        publish_result = {
            "processed": True,
        }

        if on_candle:
            on_candle(
                self.candle,
                publish_result,
            )

        return 1


class FakeStrategyRunner:

    def __init__(
        self,
        *,
        action=TradingActionV2.BUY,
    ):
        self.action = action

    def run(self, context):

        if self.action is TradingActionV2.BUY:
            metadata = {
                "stop_loss": 19950.0,
                "take_profit": 20100.0,
            }
        elif self.action is TradingActionV2.SELL:
            metadata = {
                "stop_loss": 20050.0,
                "take_profit": 19900.0,
            }
        else:
            metadata = {}

        return TradingDecisionV2(
            action=self.action,
            confidence=0.95,
            reason="TEST DECISION",
            metadata=metadata,
        )


class FakeTradeExecutor:

    def __init__(self):
        self.calls = []

    def execute(
        self,
        *,
        symbol,
        direction,
        entry,
        stop_loss,
        take_profit,
        contracts,
        risk_amount,
        approved,
    ):
        result = {
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "contracts": contracts,
            "risk_amount": risk_amount,
            "approved": approved,
        }

        self.calls.append(
            result
        )

        return result


def build_session(
    *,
    action=TradingActionV2.BUY,
    executor=None,
    candle=None,
):
    return BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(
            candle=candle,
        ),
        strategy_runner_v2=FakeStrategyRunner(
            action=action,
        ),
        trade_executor_v2=executor,
    )


def test_backtest_session_executes_buy_trade():

    executor = FakeTradeExecutor()

    session = build_session(
        action=TradingActionV2.BUY,
        executor=executor,
    )

    processed = session.run()

    assert processed == 1
    assert len(executor.calls) == 1
    assert len(session.decisions) == 1

    call = executor.calls[0]

    assert call["symbol"] == "NQ"
    assert call["direction"] == "BUY"
    assert call["entry"] == 20000.0
    assert call["stop_loss"] == 19950.0
    assert call["take_profit"] == 20100.0
    assert call["contracts"] == 1
    assert call["risk_amount"] == 250.0
    assert call["approved"] is True


def test_backtest_session_executes_sell_trade():

    executor = FakeTradeExecutor()

    session = build_session(
        action=TradingActionV2.SELL,
        executor=executor,
    )

    session.run()

    assert len(executor.calls) == 1

    call = executor.calls[0]

    assert call["direction"] == "SELL"
    assert call["symbol"] == "NQ"
    assert call["entry"] == 20000.0
    assert call["stop_loss"] == 20050.0
    assert call["take_profit"] == 19900.0
    assert call["contracts"] == 1
    assert call["risk_amount"] == 250.0
    assert call["approved"] is True


def test_backtest_session_does_not_execute_hold():

    executor = FakeTradeExecutor()

    session = build_session(
        action=TradingActionV2.HOLD,
        executor=executor,
    )

    processed = session.run()

    assert processed == 1
    assert executor.calls == []
    assert len(session.decisions) == 1
    assert (
        session.decisions[0].action
        is TradingActionV2.HOLD
    )


def test_backtest_session_works_without_executor():

    session = build_session(
        action=TradingActionV2.BUY,
        executor=None,
    )

    processed = session.run()

    assert processed == 1
    assert len(session.decisions) == 1
    assert (
        session.decisions[0].action
        is TradingActionV2.BUY
    )


def test_rejects_invalid_trade_executor():

    with pytest.raises(
        TypeError,
        match="execute",
    ):
        build_session(
            executor=object(),
        )


def test_trade_execution_requires_symbol():

    executor = FakeTradeExecutor()

    session = build_session(
        executor=executor,
        candle={
            "close": 20000.0,
        },
    )

    with pytest.raises(
        ValueError,
        match="symbol",
    ):
        session.run()


def test_trade_execution_requires_positive_close():

    executor = FakeTradeExecutor()

    session = build_session(
        executor=executor,
        candle={
            "symbol": "NQ",
            "close": 0.0,
        },
    )

    with pytest.raises(
        ValueError,
        match="close",
    ):
        session.run()
