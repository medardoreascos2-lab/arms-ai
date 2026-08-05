
from backend.backtesting.strategy_decision_engine_v2 import (
    StrategyDecisionEngineV2,
)



def test_execute_decision_when_conditions_are_valid():

    engine = StrategyDecisionEngineV2()


    result = engine.decide(

        strategy={
            "strategy_id": "STR-001",
            "confidence": 92,
        },

        market_context={
            "trend": "BULLISH",
            "structure": "BOS_CONFIRMED",
            "risk_allowed": True,
        },

    )


    assert result["decision"] == (
        "EXECUTE"
    )


    assert result["direction"] == (
        "BUY"
    )


    assert result["confidence"] == 92



def test_block_decision_when_risk_is_not_allowed():

    engine = StrategyDecisionEngineV2()


    result = engine.decide(

        strategy={
            "strategy_id": "STR-001",
            "confidence": 90,
        },

        market_context={
            "trend": "BULLISH",
            "structure": "BOS_CONFIRMED",
            "risk_allowed": False,
        },

    )


    assert result["decision"] == (
        "BLOCK"
    )



def test_block_without_strategy():

    engine = StrategyDecisionEngineV2()


    result = engine.decide(

        strategy=None,

        market_context={
            "risk_allowed": True,
        },

    )


    assert result["decision"] == (
        "BLOCK"
    )
