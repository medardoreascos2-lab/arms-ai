
from backend.backtesting.strategy_decision_engine_v2 import (
    StrategyDecisionEngineV2,
)

from backend.backtesting.strategy_decision_service_v2 import (
    StrategyDecisionServiceV2,
)



class FakeSelectionService:


    def get_selected_strategy(
        self,
    ):

        return {

            "strategy_id": "STR-001",

            "strategy_name": "EMA50 Smart Money",

            "confidence": 95,

        }



def test_strategy_decision_service_returns_decision():


    service = StrategyDecisionServiceV2(

        selection_service=(
            FakeSelectionService()
        ),

        decision_engine=(
            StrategyDecisionEngineV2()
        ),

    )


    result = service.get_decision(

        market_context={

            "trend": "BULLISH",

            "structure": "BREAKOUT",

        }

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



def test_strategy_decision_service_without_strategy():


    class EmptySelectionService:


        def get_selected_strategy(
            self,
        ):

            return None



    service = StrategyDecisionServiceV2(

        selection_service=(
            EmptySelectionService()
        ),

        decision_engine=(
            StrategyDecisionEngineV2()
        ),

    )


    result = service.get_decision(

        market_context={}

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
