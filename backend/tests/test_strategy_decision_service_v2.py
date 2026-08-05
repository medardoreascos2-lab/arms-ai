
from backend.backtesting.strategy_decision_engine_v2 import (
    StrategyDecisionEngineV2,
)

from backend.backtesting.strategy_decision_service_v2 import (
    StrategyDecisionServiceV2,
)



class FakeRecommendationService:

    def recommend(
        self,
        *,
        market_context,
    ):

        return {
            "strategy_id": "STR-001",
            "name": "EMA50 Smart Money",
            "confidence": 92,
        }



def test_decision_service_executes_valid_strategy():

    service = StrategyDecisionServiceV2(
        recommendation_service=(
            FakeRecommendationService()
        ),
        decision_engine=(
            StrategyDecisionEngineV2()
        ),
    )


    result = service.decide(
        market_context={
            "trend": "BULLISH",
            "structure": "BOS_CONFIRMED",
            "risk_allowed": True,
        }
    )


    assert result["decision"] == (
        "EXECUTE"
    )


    assert result["direction"] == (
        "BUY"
    )


    assert result["confidence"] == 92



def test_decision_service_blocks_invalid_market():

    service = StrategyDecisionServiceV2(
        recommendation_service=(
            FakeRecommendationService()
        ),
        decision_engine=(
            StrategyDecisionEngineV2()
        ),
    )


    result = service.decide(
        market_context={
            "trend": "RANGING",
            "structure": "NONE",
            "risk_allowed": True,
        }
    )


    assert result["decision"] == (
        "BLOCK"
    )



def test_decision_service_without_strategy():

    class EmptyRecommendation:

        def recommend(
            self,
            *,
            market_context,
        ):
            return None


    service = StrategyDecisionServiceV2(
        recommendation_service=(
            EmptyRecommendation()
        ),
        decision_engine=(
            StrategyDecisionEngineV2()
        ),
    )


    result = service.decide(
        market_context={
            "risk_allowed": True,
        }
    )


    assert result["decision"] == (
        "BLOCK"
    )
