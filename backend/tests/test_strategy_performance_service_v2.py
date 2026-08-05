
from backend.analytics.strategy_performance_analyzer_v2 import (
    StrategyPerformanceAnalyzerV2,
)

from backend.analytics.strategy_performance_service_v2 import (
    StrategyPerformanceServiceV2,
)



class FakeJournal:


    def get_closed_trades(
        self,
    ):

        return [

            {
                "strategy_id": "STR-001",
                "strategy_name": "EMA50 Smart Money",
                "result": "WIN",
                "profit": 200,
            },

            {
                "strategy_id": "STR-001",
                "strategy_name": "EMA50 Smart Money",
                "result": "LOSS",
                "profit": -50,
            },

            {
                "strategy_id": "STR-002",
                "strategy_name": "Breakout",
                "result": "WIN",
                "profit": 100,
            },

        ]



def test_strategy_performance_service_returns_ranking():


    service = StrategyPerformanceServiceV2(

        journal=(
            FakeJournal()
        ),

        analyzer=(
            StrategyPerformanceAnalyzerV2()
        ),

    )


    result = service.get_strategy_performance()



    assert (
        result["best_strategy"]["strategy_id"]
        ==
        "STR-001"
    )


    assert (
        result["strategies"]["STR-001"]["net_profit"]
        ==
        150
    )



def test_strategy_performance_service_invalid_history():


    class EmptyJournal:


        def get_closed_trades(
            self,
        ):

            return None



    service = StrategyPerformanceServiceV2(

        journal=(
            EmptyJournal()
        ),

        analyzer=(
            StrategyPerformanceAnalyzerV2()
        ),

    )


    result = service.get_strategy_performance()


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_HISTORY"
    )
