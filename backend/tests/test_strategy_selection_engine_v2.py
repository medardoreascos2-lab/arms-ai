
from backend.backtesting.strategy_selection_engine_v2 import (
    StrategySelectionEngineV2,
)


def test_strategy_selection_engine_selects_best_strategy():

    engine = StrategySelectionEngineV2()


    result = engine.select(

        strategies=[
            {
                "strategy_id": "STR-001",
                "strategy_name": "EMA50 Smart Money",
                "ranking_score": 95,
            },
            {
                "strategy_id": "STR-002",
                "strategy_name": "Breakout",
                "ranking_score": 70,
            },
        ],

        market_context={
            "trend": "BULLISH",
        },

    )


    assert (
        result["strategy_id"]
        ==
        "STR-001"
    )


def test_strategy_selection_engine_empty():

    engine = StrategySelectionEngineV2()


    result = engine.select(

        strategies=[],

        market_context={},

    )


    assert (
        result["status"]
        ==
        "BLOCKED"
    )
