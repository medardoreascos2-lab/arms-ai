
from backend.execution.performance_dashboard_provider_v2 import (
    PerformanceDashboardProviderV2,
)



class FakePerformanceService:


    def get_performance(
        self,
    ):

        return {

            "total_trades": 10,

            "winning_trades": 7,

            "losing_trades": 3,

            "win_rate": 70.0,

            "net_profit": 1250,

        }



def test_dashboard_provider_exposes_performance():


    provider = PerformanceDashboardProviderV2(

        performance_service=(
            FakePerformanceService()
        ),

    )


    result = provider.get_performance()



    assert result["total_trades"] == 10


    assert result["winning_trades"] == 7


    assert result["win_rate"] == 70.0


    assert result["net_profit"] == 1250





def test_dashboard_provider_without_performance():


    class EmptyPerformanceService:


        def get_performance(
            self,
        ):

            return None



    provider = PerformanceDashboardProviderV2(

        performance_service=(
            EmptyPerformanceService()
        ),

    )


    result = provider.get_performance()



    assert result is None
