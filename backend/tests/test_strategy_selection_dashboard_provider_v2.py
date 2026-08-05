
from backend.backtesting.strategy_selection_dashboard_provider_v2 import (
    StrategySelectionDashboardProviderV2,
)



class FakeSelectionService:


    def select(
        self,
        *,
        market_context,
    ):

        return {

            "strategy_id": "STR-001",

            "strategy_name": "EMA50 Smart Money",

            "confidence": 95,

        }



def test_strategy_selection_dashboard_provider_exposes_data():


    provider = StrategySelectionDashboardProviderV2(

        strategy_selection_service=(

            FakeSelectionService()

        ),

    )


    result = provider.get_selection(

        market_context={

            "trend": "BULLISH"

        }

    )


    assert (

        result["strategy_id"]

        ==

        "STR-001"

    )


    assert (

        result["confidence"]

        ==

        95

    )



def test_strategy_selection_dashboard_provider_without_data():


    class EmptyService:


        def select(

            self,

            *,

            market_context,

        ):

            return None



    provider = StrategySelectionDashboardProviderV2(

        strategy_selection_service=(

            EmptyService()

        ),

    )


    result = provider.get_selection(

        market_context={}

    )


    assert result is None
