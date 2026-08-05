
from backend.backtesting.strategy_registry_v2 import (
    StrategyRegistryV2,
)

from backend.backtesting.strategy_ranking_engine_v2 import (
    StrategyRankingEngineV2,
)

from backend.backtesting.strategy_ranking_service_v2 import (
    StrategyRankingServiceV2,
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
    }



def test_service_returns_ranked_strategies():

    registry = StrategyRegistryV2()

    registry.register(
        build_strategy()
    )


    service = StrategyRankingServiceV2(
        registry=registry,
        ranking_engine=StrategyRankingEngineV2(),
    )


    result = service.rank()


    assert result[0]["strategy_id"] == (
        "STR-001"
    )


    assert result[0]["rank"] == 1



def test_service_empty_registry():

    registry = StrategyRegistryV2()


    service = StrategyRankingServiceV2(
        registry=registry,
        ranking_engine=StrategyRankingEngineV2(),
    )


    result = service.rank()


    assert result == []
