
from backend.backtesting.strategy_ranking_engine_v2 import (
    StrategyRankingEngineV2,
)



def test_strategy_ranking_engine_scores_strategies():


    engine = StrategyRankingEngineV2()


    result = engine.rank(

        strategies=[

            {
                "strategy_id": "STR-001",
                "strategy_name": "EMA50 Smart Money",
                "win_rate": 70,
                "net_profit": 1500,
                "drawdown": 200,
                "trades": 50,
            },


            {
                "strategy_id": "STR-002",
                "strategy_name": "Breakout",
                "win_rate": 50,
                "net_profit": 300,
                "drawdown": 500,
                "trades": 20,
            },

        ]

    )


    assert (
        result["ranking"][0]["strategy_id"]
        ==
        "STR-001"
    )


    assert (
        result["ranking"][0]["score"]
        >
        result["ranking"][1]["score"]
    )



def test_strategy_ranking_engine_empty_data():


    engine = StrategyRankingEngineV2()


    result = engine.rank(
        strategies=[]
    )


    assert (
        result["total_strategies"]
        ==
        0
    )



def test_strategy_ranking_engine_invalid_data():


    engine = StrategyRankingEngineV2()


    result = engine.rank(
        strategies=None
    )


    assert (
        result["status"]
        ==
        "BLOCKED"
    )


    assert (
        result["reason"]
        ==
        "INVALID_HISTORY"
    )
