import pytest

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreResultV2,
)
from backend.backtesting.institutional_backtesting_report_v2 import (
    InstitutionalBacktestingReportV2,
)
from backend.models.backtest_result import BacktestResult
from backend.models.backtest_statistics import (
    BacktestStatistics,
)


def build_backtest():

    result = BacktestResult(
        total_candles=1000,
        total_signals=140,
        authorized_trades=120,
        blocked_signals=20,
    )

    result.statistics = BacktestStatistics(
        total_trades=120,
        winning_trades=84,
        losing_trades=36,
        gross_profit=2400.0,
        gross_loss=-700.0,
        net_profit=1700.0,
        win_rate=70.0,
        profit_factor=2.5,
        expectancy=45.0,
        max_drawdown=180.0,
    )

    return result


def build_score():

    return BacktestCompositeScoreResultV2(
        score=91.4,
        grade="A+",
        strengths=[
            "HIGH_PROFIT_FACTOR",
            "HIGH_WIN_RATE",
        ],
        weaknesses=[],
        components={
            "net_pnl":25.0,
            "win_rate":20.0,
            "profit_factor":20.0,
            "expectancy":12.0,
            "maximum_drawdown":14.4,
        },
    )


def test_build_report():

    report = InstitutionalBacktestingReportV2(
        backtest_result=build_backtest(),
        score_result=build_score(),
        certification_status="CERTIFIED",
    )

    payload = report.to_dict()

    assert payload["executive_summary"]["grade"] == "A+"
    assert payload["executive_summary"]["status"] == "CERTIFIED"

    assert payload["performance"]["net_profit"] == 1700.0
    assert payload["performance"]["profit_factor"] == 2.5

    assert payload["score"]["score"] == 91.4

    assert payload["strengths"] == [
        "HIGH_PROFIT_FACTOR",
        "HIGH_WIN_RATE",
    ]

    assert payload["weaknesses"] == []


def test_requires_backtest():

    with pytest.raises(TypeError):

        InstitutionalBacktestingReportV2(
            backtest_result=None,
            score_result=build_score(),
            certification_status="CERTIFIED",
        )


def test_requires_score():

    with pytest.raises(TypeError):

        InstitutionalBacktestingReportV2(
            backtest_result=build_backtest(),
            score_result=None,
            certification_status="CERTIFIED",
        )
