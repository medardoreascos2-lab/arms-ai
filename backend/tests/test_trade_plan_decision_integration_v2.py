
from backend.backtesting.trade_plan_engine_v2 import (
    TradePlanEngineV2,
)



def test_trade_plan_engine_creates_plan_from_decision():


    engine = TradePlanEngineV2()


    result = engine.create_plan(

        decision={

            "decision": "EXECUTE",

            "direction": "BUY",

            "strategy_id": "STR-001",

            "confidence": 94,

        },

        market_context={

            "price": 23500,

        },

    )


    assert (

        result["status"]

        ==

        "READY"

    )


    assert (

        result["direction"]

        ==

        "BUY"

    )


    assert (

        result["strategy_id"]

        ==

        "STR-001"

    )



def test_trade_plan_engine_blocks_without_execution_decision():


    engine = TradePlanEngineV2()


    result = engine.create_plan(

        decision={

            "decision": "BLOCK",

        },

        market_context={

            "price": 23500,

        },

    )


    assert (

        result["status"]

        ==

        "BLOCKED"

    )


    assert (

        result["reason"]

        ==

        "DECISION_NOT_EXECUTABLE"

    )
