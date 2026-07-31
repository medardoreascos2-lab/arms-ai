from backend.backtesting.backtest_session_v2 import (
    BacktestSessionV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
)


class FakeBacktestRunner:

    def run(self, *, on_candle=None):

        for index in range(3):

            candle = {
                "index": index,
            }

            publish_result = {
                "processed": True,
            }

            if on_candle:
                on_candle(
                    candle,
                    publish_result,
                )

        return 3


class FakeStrategyRunner:

    def __init__(self):
        self.calls = []

    def run(self, context):

        self.calls.append(context)

        return TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=0.50,
            reason="Test",
        )


def test_session_runs_complete_backtest():

    strategy = FakeStrategyRunner()

    session = BacktestSessionV2(
        backtest_runner_v2=FakeBacktestRunner(),
        strategy_runner_v2=strategy,
    )

    processed = session.run()

    assert processed == 3
    assert len(strategy.calls) == 3

    assert strategy.calls[0]["candle"]["index"] == 0
    assert strategy.calls[1]["candle"]["index"] == 1
    assert strategy.calls[2]["candle"]["index"] == 2
