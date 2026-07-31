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

        return TradingDecisionV2(
            action=self.action,
            confidence=0.95,
            reason="TEST DECISION",
        )


class FakeTradeExecutor:

    def __init__(self):
        self.calls = []

    def execute(
        self,
        *,
        symbol,
        decision,
        price,
        quantity,
    ):
        self.calls.append(
            {
                "symbol": symbol,
                "decision": decision,
                "price": price,
                "quantity": quantity,
            }
        )


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
    assert call["decision"].action is TradingActionV2.BUY
    assert call["price"] == 20000.0
    assert call["quantity"] == 1.0


def test_backtest_session_executes_sell_trade():

    executor = FakeTradeExecutor()

    session = build_session(
        action=TradingActionV2.SELL,
        executor=executor,
    )

    session.run()

    assert len(executor.calls) == 1

    call = executor.calls[0]

    assert call["decision"].action is TradingActionV2.SELL
    assert call["symbol"] == "NQ"
    assert call["price"] == 20000.0
    assert call["quantity"] == 1.0


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
