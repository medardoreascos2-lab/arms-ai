import pytest

from backend.strategies.strategy_runner_v2 import (
    StrategyRunnerV2,
)

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
    TradingStrategyV2,
)


class BuyStrategy(TradingStrategyV2):

    def evaluate(self, context):

        return TradingDecisionV2(
            action=TradingActionV2.BUY,
            confidence=0.90,
            reason="Test BUY",
        )


class InvalidStrategy(TradingStrategyV2):

    def evaluate(self, context):
        return "INVALID"


def test_runner_returns_decision():

    runner = StrategyRunnerV2(
        strategy=BuyStrategy(),
    )

    decision = runner.run(
        {
            "symbol": "NQ",
        }
    )

    assert decision.action is TradingActionV2.BUY
    assert decision.confidence == 0.90
    assert decision.reason == "Test BUY"


def test_runner_rejects_invalid_result():

    runner = StrategyRunnerV2(
        strategy=InvalidStrategy(),
    )

    with pytest.raises(
        TypeError,
        match="TradingDecisionV2",
    ):
        runner.run({})
