
from backend.backtesting.strategy_registry_v2 import (
    StrategyRegistryV2,
)

from backend.backtesting.strategy_ranking_engine_v2 import (
    StrategyRankingEngineV2,
)

from backend.backtesting.strategy_ranking_service_v2 import (
    StrategyRankingServiceV2,
)

from backend.backtesting.strategy_recommendation_engine_v2 import (
    StrategyRecommendationEngineV2,
)

from backend.backtesting.strategy_recommendation_service_v2 import (
    StrategyRecommendationServiceV2,
)



def build_strategy():

    return {
        "strategy_id": "STR-001",
        "name": "EMA50 Smart Money",
        "version": "1.0",
        "status": "CERTIFIED",
        "grade": "A",
        "validation_score": 92.0,
        "performance_score": 85.0,
        "market_conditions": [
            "TRENDING",
            "LOW_VOLATILITY",
        ],
    }



def test_service_recommends_strategy():

    registry = StrategyRegistryV2()


    registry.register(
        build_strategy()
    )


    ranking_service = StrategyRankingServiceV2(
        registry=registry,
        ranking_engine=StrategyRankingEngineV2(),
    )


    service = StrategyRecommendationServiceV2(
        ranking_service=ranking_service,
        recommendation_engine=StrategyRecommendationEngineV2(),
    )


    result = service.recommend(
        market_context={
            "regime": "TRENDING",
            "volatility": "LOW_VOLATILITY",
        }
    )


    assert result["strategy_id"] == (
        "STR-001"
    )


    assert result["confidence"] > 0



def test_service_without_match():

    registry = StrategyRegistryV2()


    registry.register(
        build_strategy()
    )


    service = StrategyRecommendationServiceV2(
        ranking_service=StrategyRankingServiceV2(
            registry=registry,
            ranking_engine=StrategyRankingEngineV2(),
        ),
        recommendation_engine=StrategyRecommendationEngineV2(),
    )


    result = service.recommend(
        market_context={
            "regime": "RANGING",
            "volatility": "EXTREME",
        }
    )


    assert result is None
