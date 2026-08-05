
from backend.backtesting.strategy_ranking_engine_v2 import (
    StrategyRankingEngineV2,
)

from backend.backtesting.strategy_ranking_service_v2 import (
    StrategyRankingServiceV2,
)



class FakeStrategyProvider:


    def get_strategies(
        self,
    ):

        return [

            {
                "strategy_id": "STR-001",
                "strategy_name": "EMA50 Smart Money",
                "win_rate": 70,
                "net_profit": 1500,
                "drawdown": 200,
                "trades": 50,
            },


            {
                "strategy_id": "STR-002",
                "strategy_name": "Breakout",
                "win_rate": 50,
                "net_profit": 300,
                "drawdown": 500,
                "trades": 20,
            },

        ]



def test_strategy_ranking_service_returns_ranking():


    service = StrategyRankingServiceV2(

        strategy_provider=(
            FakeStrategyProvider()
        ),

        engine=(
            StrategyRankingEngineV2()
        ),

    )


    result = service.get_ranking()



    assert (
        result["ranking"][0]["strategy_id"]
        ==
        "STR-001"
    )


    assert (
        result["ranking"][0]["rank"]
        ==
        1
    )



def test_strategy_ranking_service_invalid_history():


    class EmptyProvider:


        def get_strategies(
            self,
        ):

            return None



    service = StrategyRankingServiceV2(

        strategy_provider=(
            EmptyProvider()
        ),

        engine=(
            StrategyRankingEngineV2()
        ),

    )


    result = service.get_ranking()



    assert (
        result["status"]
        ==
        "BLOCKED"
    )


    assert (
        result["reason"]
        ==
        "INVALID_HISTORY"
    )
