
from backend.backtesting.strategy_recommendation_engine_v2 import (
    StrategyRecommendationEngineV2,
)



def build_strategies():

    return [

        {
            "strategy_id": "STR-001",
            "name": "EMA50 Smart Money",
            "ranking_score": 92.0,
            "market_conditions": [
                "TRENDING",
                "LOW_VOLATILITY",
            ],
        },

        {
            "strategy_id": "STR-002",
            "name": "Breakout Strategy",
            "ranking_score": 80.0,
            "market_conditions": [
                "HIGH_VOLATILITY",
            ],
        },

    ]



def test_recommend_strategy_for_market():

    engine = StrategyRecommendationEngineV2()


    result = engine.recommend(
        strategies=build_strategies(),
        market_context={
            "regime": "TRENDING",
            "volatility": "LOW_VOLATILITY",
        },
    )


    assert result["strategy_id"] == (
        "STR-001"
    )


    assert result["confidence"] > 0



def test_no_matching_strategy():

    engine = StrategyRecommendationEngineV2()


    result = engine.recommend(
        strategies=build_strategies(),
        market_context={
            "regime": "RANGING",
            "volatility": "EXTREME",
        },
    )


    assert result is None
