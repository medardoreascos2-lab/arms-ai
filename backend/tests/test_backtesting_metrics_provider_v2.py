from backend.backtesting.backtesting_metrics_provider_v2 import (
    BacktestingMetricsProviderV2,
)


class FakeEngine:

    def calculate(
        self,
        trades,
    ):

        return {
            "total_trades": len(trades),
            "winning_trades": 1,
            "losing_trades": 1,
            "win_rate": 50.0,
            "profit_factor": 2.0,
            "net_profit": 100.0,
            "max_drawdown": -50.0,
        }


def test_metrics_provider_uses_engine():

    provider = BacktestingMetricsProviderV2(
        engine=FakeEngine(),
    )

    provider.add_trade(
        {
            "pnl": 100,
        }
    )

    provider.add_trade(
        {
            "pnl": -50,
        }
    )

    metrics = provider.get_metrics()

    assert metrics == {
        "total_trades": 2,
        "winning_trades": 1,
        "losing_trades": 1,
        "win_rate": 50.0,
        "profit_factor": 2.0,
        "net_profit": 100.0,
        "max_drawdown": -50.0,
    }


def test_provider_starts_empty():

    provider = BacktestingMetricsProviderV2(
        engine=FakeEngine(),
    )

    assert provider.get_trades() == []


def test_invalid_engine():

    try:

        BacktestingMetricsProviderV2(
            engine=object(),
        )

    except TypeError as exc:

        assert "engine" in str(exc)

    else:

        raise AssertionError(
            "Se esperaba TypeError."
        )
