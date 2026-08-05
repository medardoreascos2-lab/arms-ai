
from backend.analytics.strategy_performance_analyzer_v2 import (
    StrategyPerformanceAnalyzerV2,
)



def test_strategy_performance_analyzer_ranks_strategies():


    analyzer = StrategyPerformanceAnalyzerV2()


    result = analyzer.analyze(

        trades=[

            {
                "strategy_id": "STR-001",
                "strategy_name": "EMA50 Smart Money",
                "result": "WIN",
                "profit": 200,
            },

            {
                "strategy_id": "STR-001",
                "strategy_name": "EMA50 Smart Money",
                "result": "LOSS",
                "profit": -50,
            },

            {
                "strategy_id": "STR-002",
                "strategy_name": "Breakout",
                "result": "WIN",
                "profit": 100,
            },

        ]

    )


    assert (
        result["best_strategy"]["strategy_id"]
        ==
        "STR-001"
    )


    assert (
        result["strategies"]["STR-001"]["win_rate"]
        ==
        50.0
    )


    assert (
        result["strategies"]["STR-001"]["net_profit"]
        ==
        150
    )



def test_strategy_performance_analyzer_empty_history():


    analyzer = StrategyPerformanceAnalyzerV2()


    result = analyzer.analyze(
        trades=[]
    )


    assert result["total_trades"] == 0



def test_strategy_performance_analyzer_invalid_history():


    analyzer = StrategyPerformanceAnalyzerV2()


    result = analyzer.analyze(
        trades=None
    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_HISTORY"
    )
