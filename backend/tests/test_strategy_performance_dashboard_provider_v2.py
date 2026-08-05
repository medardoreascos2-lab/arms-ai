
from backend.analytics.strategy_performance_dashboard_provider_v2 import (
    StrategyPerformanceDashboardProviderV2,
)



class FakeStrategyPerformanceService:


    def get_strategy_performance(
        self,
    ):

        return {

            "total_trades": 10,

            "strategies": {

                "STR-001": {

                    "strategy_id": "STR-001",

                    "strategy_name": "EMA50 Smart Money",

                    "win_rate": 70.0,

                    "net_profit": 1500,

                }

            },

            "best_strategy": {

                "strategy_id": "STR-001",

                "strategy_name": "EMA50 Smart Money",

            },

        }



def test_strategy_performance_dashboard_provider_exposes_data():


    provider = StrategyPerformanceDashboardProviderV2(

        strategy_performance_service=(

            FakeStrategyPerformanceService()

        ),

    )


    result = provider.get_strategy_performance()



    assert (

        result["best_strategy"]["strategy_id"]

        ==

        "STR-001"

    )


    assert (

        result["strategies"]["STR-001"]["win_rate"]

        ==

        70.0

    )



def test_strategy_performance_dashboard_provider_without_data():


    class EmptyService:


        def get_strategy_performance(
            self,
        ):

            return None



    provider = StrategyPerformanceDashboardProviderV2(

        strategy_performance_service=(

            EmptyService()

        ),

    )


    result = provider.get_strategy_performance()


    assert result is None
