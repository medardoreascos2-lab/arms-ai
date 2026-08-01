import pytest

from backend.backtesting.backtest_composite_score_v2 import (
    BacktestCompositeScoreResultV2,
    BacktestCompositeScoreV2,
)


def test_calculates_high_quality_strategy_score():

    scorer = BacktestCompositeScoreV2(
        minimum_trades=10,
    )

    result = scorer.calculate(
        metrics={
            "net_pnl": 1200.0,
            "win_rate": 0.70,
            "profit_factor": 2.40,
            "expectancy": 100.0,
            "maximum_drawdown": 150.0,
            "total_trades": 20,
        }
    )

    assert isinstance(
        result,
        BacktestCompositeScoreResultV2,
    )

    assert 0.0 <= result.score <= 100.0
    assert result.score >= 80.0
    assert result.grade in {
        "A+",
        "A",
    }

    assert (
        "HIGH_PROFIT_FACTOR"
        in result.strengths
    )

    assert (
        "LOW_DRAWDOWN"
        in result.strengths
    )

    assert result.weaknesses == []


def test_penalizes_small_sample_size():

    scorer = BacktestCompositeScoreV2(
        minimum_trades=20,
    )

    result = scorer.calculate(
        metrics={
            "net_pnl": 1000.0,
            "win_rate": 0.80,
            "profit_factor": 3.0,
            "expectancy": 200.0,
            "maximum_drawdown": 100.0,
            "total_trades": 4,
        }
    )

    assert result.score < 80.0

    assert (
        "INSUFFICIENT_TRADES"
        in result.weaknesses
    )


def test_penalizes_large_drawdown():

    scorer = BacktestCompositeScoreV2()

    result = scorer.calculate(
        metrics={
            "net_pnl": 500.0,
            "win_rate": 0.60,
            "profit_factor": 1.50,
            "expectancy": 30.0,
            "maximum_drawdown": 1200.0,
            "total_trades": 30,
        }
    )

    assert (
        "HIGH_DRAWDOWN"
        in result.weaknesses
    )

    assert result.score < 70.0


def test_negative_strategy_receives_low_grade():

    scorer = BacktestCompositeScoreV2()

    result = scorer.calculate(
        metrics={
            "net_pnl": -400.0,
            "win_rate": 0.35,
            "profit_factor": 0.75,
            "expectancy": -20.0,
            "maximum_drawdown": 600.0,
            "total_trades": 25,
        }
    )

    assert result.score < 50.0
    assert result.grade in {
        "D",
        "F",
    }

    assert (
        "NEGATIVE_NET_PNL"
        in result.weaknesses
    )


def test_to_dict_returns_safe_copy():

    scorer = BacktestCompositeScoreV2()

    result = scorer.calculate(
        metrics={
            "net_pnl": 100.0,
            "win_rate": 0.55,
            "profit_factor": 1.30,
            "expectancy": 10.0,
            "maximum_drawdown": 200.0,
            "total_trades": 15,
        }
    )

    payload = result.to_dict()

    payload["strengths"].append(
        "MODIFIED"
    )

    assert (
        "MODIFIED"
        not in result.strengths
    )


def test_rejects_invalid_metrics():

    scorer = BacktestCompositeScoreV2()

    with pytest.raises(
        TypeError,
        match="metrics",
    ):
        scorer.calculate(
            metrics=[]
        )


@pytest.mark.parametrize(
    "minimum_trades",
    [
        0,
        -1,
        "10",
    ],
)
def test_rejects_invalid_minimum_trades(
    minimum_trades,
):

    with pytest.raises(
        (
            TypeError,
            ValueError,
        ),
    ):
        BacktestCompositeScoreV2(
            minimum_trades=minimum_trades,
        )
