from backend.backtesting.backtesting_performance_report_v2 import (
    BacktestingPerformanceReportV2,
)


def build_metrics():

    return {
        "total_trades": 100,
        "winning_trades": 65,
        "losing_trades": 35,
        "win_rate": 65.0,
        "profit_factor": 2.1,
        "net_profit": 5000.0,
        "max_drawdown": -800.0,
    }


def test_performance_report_generates_summary():

    report = BacktestingPerformanceReportV2()

    result = report.generate(
        build_metrics()
    )

    assert result == {
        "score": 85,
        "rating": "GOOD",
        "metrics": build_metrics(),
    }


def test_bad_performance_rating():

    report = BacktestingPerformanceReportV2()

    result = report.generate(
        {
            "total_trades": 20,
            "winning_trades": 5,
            "losing_trades": 15,
            "win_rate": 25.0,
            "profit_factor": 0.7,
            "net_profit": -1000.0,
            "max_drawdown": -2000.0,
        }
    )

    assert result["rating"] == "BAD"


def test_invalid_metrics():

    report = BacktestingPerformanceReportV2()

    try:

        report.generate(
            {
                "wrong": 100,
            }
        )

    except ValueError as exc:

        assert "metrics" in str(exc)

    else:

        raise AssertionError(
            "Se esperaba ValueError."
        )
