import pytest

from backend.strategies.trading_strategy_v2 import (
    TradingActionV2,
    TradingDecisionV2,
    TradingStrategyV2,
)


class ExampleStrategy(TradingStrategyV2):

    def evaluate(self, context):
        return TradingDecisionV2(
            action=TradingActionV2.BUY,
            confidence=0.85,
            reason="Tendencia alcista confirmada",
            metadata={
                "symbol": context["symbol"],
            },
        )


def test_strategy_returns_structured_decision():

    strategy = ExampleStrategy()

    decision = strategy.evaluate(
        {
            "symbol": "NQ",
        }
    )

    assert isinstance(
        decision,
        TradingDecisionV2,
    )

    assert decision.action is TradingActionV2.BUY
    assert decision.confidence == 0.85
    assert decision.reason == "Tendencia alcista confirmada"
    assert decision.metadata == {
        "symbol": "NQ",
    }


def test_trading_actions_are_available():

    assert TradingActionV2.BUY.value == "BUY"
    assert TradingActionV2.SELL.value == "SELL"
    assert TradingActionV2.HOLD.value == "HOLD"


def test_decision_uses_empty_metadata_by_default():

    decision = TradingDecisionV2(
        action=TradingActionV2.HOLD,
        confidence=0.0,
        reason="Sin configuración válida",
    )

    assert decision.metadata == {}


@pytest.mark.parametrize(
    "confidence",
    [
        -0.01,
        1.01,
    ],
)
def test_decision_rejects_invalid_confidence(
    confidence,
):

    with pytest.raises(
        ValueError,
        match="confidence",
    ):
        TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=confidence,
            reason="Prueba",
        )


def test_decision_rejects_invalid_action():

    with pytest.raises(
        TypeError,
        match="action",
    ):
        TradingDecisionV2(
            action="BUY",
            confidence=0.80,
            reason="Prueba",
        )


def test_decision_rejects_empty_reason():

    with pytest.raises(
        ValueError,
        match="reason",
    ):
        TradingDecisionV2(
            action=TradingActionV2.HOLD,
            confidence=0.0,
            reason="   ",
        )


def test_base_strategy_cannot_be_instantiated():

    with pytest.raises(TypeError):
        TradingStrategyV2()
