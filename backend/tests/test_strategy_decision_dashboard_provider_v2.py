
from backend.backtesting.strategy_decision_dashboard_provider_v2 import (
    StrategyDecisionDashboardProviderV2,
)



class FakeDecisionService:

    def decide(
        self,
        *,
        market_context,
    ):

        return {
            "decision": "EXECUTE",
            "direction": "BUY",
            "confidence": 92,
        }



def test_dashboard_provider_exposes_decision():


    provider = StrategyDecisionDashboardProviderV2(
        decision_service=(
            FakeDecisionService()
        ),
    )


    result = provider.get_decision()


    assert result["decision"] == (
        "EXECUTE"
    )


    assert result["direction"] == (
        "BUY"
    )


    assert result["confidence"] == 92



def test_dashboard_provider_without_service():


    class EmptyDecision:

        def decide(
            self,
            *,
            market_context,
        ):
            return None



    provider = StrategyDecisionDashboardProviderV2(
        decision_service=(
            EmptyDecision()
        ),
    )


    result = provider.get_decision()


    assert result is None
