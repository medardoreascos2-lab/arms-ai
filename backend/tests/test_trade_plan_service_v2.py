
from backend.backtesting.trade_plan_service_v2 import (
    TradePlanServiceV2,
)

from backend.backtesting.trade_plan_engine_v2 import (
    TradePlanEngineV2,
)



class FakeDecisionService:


    def get_decision(
        self,
        *,
        market_context,
    ):

        return {
            "decision": "EXECUTE",
            "direction": "BUY",
            "strategy_id": "STR-001",
            "confidence": 94,
        }



def test_trade_plan_service_creates_plan():


    service = TradePlanServiceV2(

        decision_service=(
            FakeDecisionService()
        ),

        trade_plan_engine=(
            TradePlanEngineV2()
        ),

    )


    result = service.create_trade_plan(

        market_context={

            "price": 23500,

        }

    )


    assert (

        result["status"]

        ==

        "READY"

    )


    assert (

        result["strategy_id"]

        ==

        "STR-001"

    )



def test_trade_plan_service_blocks_without_decision():


    class EmptyDecisionService:


        def get_decision(
            self,
            *,
            market_context,
        ):

            return {

                "decision": "BLOCK"

            }



    service = TradePlanServiceV2(

        decision_service=(

            EmptyDecisionService()

        ),

        trade_plan_engine=(

            TradePlanEngineV2()

        ),

    )


    result = service.create_trade_plan(

        market_context={}

    )


    assert (

        result["status"]

        ==

        "BLOCKED"

    )
