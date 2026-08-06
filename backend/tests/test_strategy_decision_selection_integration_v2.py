
from backend.backtesting.strategy_decision_engine_v2 import (
    StrategyDecisionEngineV2,
)



def test_strategy_decision_engine_accepts_selected_strategy():


    engine = StrategyDecisionEngineV2()


    result = engine.decide(

        selected_strategy={

            "strategy_id": "STR-001",

            "strategy_name": "EMA50 Smart Money",

            "confidence": 95,

        },

        market_context={

            "trend": "BULLISH",

            "structure": "BREAKOUT",

        },

    )


    assert (

        result["decision"]

        ==

        "EXECUTE"

    )


    assert (

        result["strategy_id"]

        ==

        "STR-001"

    )



def test_strategy_decision_engine_blocks_without_strategy():


    engine = StrategyDecisionEngineV2()


    result = engine.decide(

        selected_strategy=None,

        market_context={},

    )


    assert (

        result["status"]

        ==

        "BLOCKED"

    )


    assert (

        result["reason"]

        ==

        "NO_SELECTED_STRATEGY"

    )
