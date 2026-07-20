import pandas as pd
import pytest

from backend.portfolio.portfolio_backtest import (
    PortfolioBacktest,
)


def build_prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "AAPL": [
                100.0,
                102.0,
                101.0,
                105.0,
            ],
            "MSFT": [
                200.0,
                204.0,
                208.0,
                210.0,
            ],
        }
    )


def test_backtest_returns_equity_curve():
    result = PortfolioBacktest().run(
        prices=build_prices(),
        weights={
            "AAPL": 0.6,
            "MSFT": 0.4,
        },
        initial_value=1000.0,
    )

    assert len(result["equity_curve"]) == 4
    assert result["equity_curve"][0] == pytest.approx(
        1000.0
    )


def test_backtest_returns_positive_final_value():
    result = PortfolioBacktest().run(
        prices=build_prices(),
        weights={
            "AAPL": 0.6,
            "MSFT": 0.4,
        },
        initial_value=1000.0,
    )

    assert result["final_value"] > 0.0


def test_backtest_returns_performance_metrics():
    result = PortfolioBacktest().run(
        prices=build_prices(),
        weights={
            "AAPL": 0.6,
            "MSFT": 0.4,
        },
        initial_value=1000.0,
    )

    assert "total_return" in result
    assert "annualized_return" in result
    assert "annualized_volatility" in result
    assert "sharpe_ratio" in result
    assert "maximum_drawdown" in result


def test_backtest_rejects_empty_prices():
    with pytest.raises(
        ValueError,
        match="prices",
    ):
        PortfolioBacktest().run(
            prices=pd.DataFrame(),
            weights={
                "AAPL": 1.0,
            },
        )


def test_backtest_rejects_invalid_weights():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        PortfolioBacktest().run(
            prices=build_prices(),
            weights={
                "AAPL": 0.2,
                "MSFT": 0.2,
            },
        )
