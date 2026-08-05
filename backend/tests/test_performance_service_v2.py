
from backend.execution.performance_analyzer_v2 import (
    PerformanceAnalyzerV2,
)

from backend.execution.performance_service_v2 import (
    PerformanceServiceV2,
)



class FakeJournal:


    def get_trades(
        self,
    ):

        return [

            {
                "trade_id": "TRD-001",
                "result": "WIN",
                "profit": 200,
            },

            {
                "trade_id": "TRD-002",
                "result": "LOSS",
                "profit": -50,
            },

        ]



def test_performance_service_returns_metrics():


    service = PerformanceServiceV2(

        journal=(
            FakeJournal()
        ),

        analyzer=(
            PerformanceAnalyzerV2()
        ),

    )


    result = service.get_performance()


    assert result["total_trades"] == 2


    assert result["winning_trades"] == 1


    assert result["losing_trades"] == 1


    assert result["net_profit"] == 150



def test_performance_service_blocks_invalid_journal():


    class EmptyJournal:


        def get_trades(
            self,
        ):

            return None



    service = PerformanceServiceV2(

        journal=(
            EmptyJournal()
        ),

        analyzer=(
            PerformanceAnalyzerV2()
        ),

    )


    result = service.get_performance()


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_HISTORY"
    )
