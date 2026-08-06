
from backend.backtesting.strategy_decision_dashboard_provider_v2 import (
    StrategyDecisionDashboardProviderV2,
)



class FakeStrategyDecisionService:


    def get_decision(
        self,
        *,
        market_context,
    ):

        return {

            "decision": "EXECUTE",

            "direction": "BUY",

            "strategy_id": "STR-001",

            "confidence": 95,

        }



def test_strategy_decision_dashboard_provider_exposes_data():


    provider = StrategyDecisionDashboardProviderV2(

        strategy_decision_service=(

            FakeStrategyDecisionService()

        ),

    )


    result = provider.get_decision(

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



def test_strategy_decision_dashboard_provider_without_data():


    class EmptyService:


        def get_decision(
            self,
            *,
            market_context,
        ):

            return None



    provider = StrategyDecisionDashboardProviderV2(

        strategy_decision_service=(

            EmptyService()

        ),

    )


    result = provider.get_decision(

        market_context={}

    )


    assert result is None
