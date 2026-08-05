
from backend.backtesting.strategy_selection_engine_v2 import (
    StrategySelectionEngineV2,
)

from backend.backtesting.strategy_selection_service_v2 import (
    StrategySelectionServiceV2,
)



class FakeRankingService:


    def rank(
        self,
    ):

        return {

            "total_strategies": 2,

            "ranking": [

                {
                    "strategy_id": "STR-001",
                    "strategy_name": "EMA50 Smart Money",
                    "ranking_score": 95,
                },

                {
                    "strategy_id": "STR-002",
                    "strategy_name": "Breakout",
                    "ranking_score": 70,
                },

            ]

        }



def test_strategy_selection_service_selects_strategy():


    service = StrategySelectionServiceV2(

        ranking_service=(
            FakeRankingService()
        ),

        selection_engine=(
            StrategySelectionEngineV2()
        ),

    )


    result = service.select(

        market_context={
            "trend": "BULLISH",
        }

    )


    assert (
        result["strategy_id"]
        ==
        "STR-001"
    )



def test_strategy_selection_service_without_strategies():


    class EmptyRankingService:


        def rank(
            self,
        ):

            return None



    service = StrategySelectionServiceV2(

        ranking_service=(
            EmptyRankingService()
        ),

        selection_engine=(
            StrategySelectionEngineV2()
        ),

    )


    result = service.select(

        market_context={}

    )


    assert (
        result["status"]
        ==
        "BLOCKED"
    )
