
from backend.backtesting.strategy_ranking_engine_v2 import (
    StrategyRankingEngineV2,
)



def build_strategies():

    return [

        {
            "strategy_id": "STR-001",
            "name": "EMA50 Smart Money",
            "validation_score": 92.0,
            "performance_score": 85.0,
            "grade": "A",
        },

        {
            "strategy_id": "STR-002",
            "name": "Breakout Strategy",
            "validation_score": 80.0,
            "performance_score": 70.0,
            "grade": "B",
        },

    ]



def test_rank_strategies():

    engine = StrategyRankingEngineV2()


    result = engine.rank(
        build_strategies()
    )


    assert result[0]["strategy_id"] == (
        "STR-001"
    )


    assert result[0]["rank"] == 1



def test_ranking_contains_score():

    engine = StrategyRankingEngineV2()


    result = engine.rank(
        build_strategies()
    )


    assert "ranking_score" in result[0]



def test_empty_strategy_list():

    engine = StrategyRankingEngineV2()


    result = engine.rank(
        []
    )


    assert result == []
