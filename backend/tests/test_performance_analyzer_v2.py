
from backend.execution.performance_analyzer_v2 import (
    PerformanceAnalyzerV2,
)



def test_performance_analyzer_calculates_metrics():


    analyzer = PerformanceAnalyzerV2()


    result = analyzer.analyze(

        trades=[

            {
                "trade_id": "TRD-001",
                "direction": "BUY",
                "result": "WIN",
                "profit": 200,
            },

            {
                "trade_id": "TRD-002",
                "direction": "SELL",
                "result": "LOSS",
                "profit": -100,
            },

        ]

    )


    assert result["total_trades"] == 2


    assert result["winning_trades"] == 1


    assert result["losing_trades"] == 1


    assert result["win_rate"] == 50.0


    assert result["net_profit"] == 100



def test_performance_analyzer_empty_history():


    analyzer = PerformanceAnalyzerV2()


    result = analyzer.analyze(
        trades=[]
    )


    assert result["total_trades"] == 0


    assert result["win_rate"] == 0



def test_performance_analyzer_invalid_history():


    analyzer = PerformanceAnalyzerV2()


    result = analyzer.analyze(
        trades=None
    )


    assert result["status"] == (
        "BLOCKED"
    )


    assert result["reason"] == (
        "INVALID_HISTORY"
    )
