
from backend.backtesting.strategy_ranking_dashboard_provider_v2 import (
    StrategyRankingDashboardProviderV2,
)



class FakeStrategyRankingService:


    def get_ranking(
        self,
    ):

        return {

            "total_strategies": 2,

            "ranking": [

                {

                    "strategy_id": "STR-001",

                    "strategy_name": "EMA50 Smart Money",

                    "score": 92,

                    "rank": 1,

                },

                {

                    "strategy_id": "STR-002",

                    "strategy_name": "Breakout",

                    "score": 70,

                    "rank": 2,

                },

            ],

        }



def test_strategy_ranking_dashboard_provider_exposes_data():


    provider = StrategyRankingDashboardProviderV2(

        strategy_ranking_service=(

            FakeStrategyRankingService()

        ),

    )


    result = provider.get_ranking()



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



def test_strategy_ranking_dashboard_provider_without_data():


    class EmptyService:


        def get_ranking(
            self,
        ):

            return None



    provider = StrategyRankingDashboardProviderV2(

        strategy_ranking_service=(

            EmptyService()

        ),

    )


    result = provider.get_ranking()


    assert result is None
