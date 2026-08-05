from backend.backtesting.backtesting_metrics_engine_v2 import (
    BacktestingMetricsEngineV2,
)


def build_trades():

    return [
        {
            "pnl": 500.0,
        },
        {
            "pnl": -200.0,
        },
        {
            "pnl": 300.0,
        },
        {
            "pnl": -100.0,
        },
    ]


def test_metrics_engine_calculates_basic_metrics():

    engine = BacktestingMetricsEngineV2()

    metrics = engine.calculate(
        build_trades()
    )

    assert metrics == {
        "total_trades": 4,
        "winning_trades": 2,
        "losing_trades": 2,
        "win_rate": 50.0,
        "profit_factor": 2.6666666667,
        "net_profit": 500.0,
        "max_drawdown": -200.0,
    }


def test_empty_trades_returns_zero_metrics():

    engine = BacktestingMetricsEngineV2()

    metrics = engine.calculate(
        []
    )

    assert metrics == {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "net_profit": 0.0,
        "max_drawdown": 0.0,
    }


def test_invalid_trade_payload():

    engine = BacktestingMetricsEngineV2()

    try:
        engine.calculate(
            [
                {
                    "wrong": 100,
                }
            ]
        )

    except ValueError as exc:

        assert "pnl" in str(exc)

    else:

        raise AssertionError(
            "Se esperaba ValueError."
        )
