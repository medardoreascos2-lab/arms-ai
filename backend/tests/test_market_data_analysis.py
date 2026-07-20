import pandas as pd
import pytest

from backend.services.market_data_analysis import (
    build_portfolio_inputs_from_prices,
)


def build_prices():
    return pd.DataFrame(
        {
            "AAPL": [
                100.0,
                101.0,
                103.0,
                102.0,
            ],
            "MSFT": [
                200.0,
                202.0,
                204.0,
                208.0,
            ],
        }
    )


def test_builds_returns_for_each_asset():
    result = build_portfolio_inputs_from_prices(
        build_prices()
    )

    assert set(result["returns"]) == {
        "AAPL",
        "MSFT",
    }

    assert len(result["returns"]["AAPL"]) == 3
    assert len(result["returns"]["MSFT"]) == 3


def test_builds_volatilities():
    result = build_portfolio_inputs_from_prices(
        build_prices()
    )

    assert set(result["volatilities"]) == {
        "AAPL",
        "MSFT",
    }

    assert result["volatilities"]["AAPL"] >= 0.0
    assert result["volatilities"]["MSFT"] >= 0.0


def test_builds_expected_returns():
    result = build_portfolio_inputs_from_prices(
        build_prices()
    )

    assert set(result["expected_returns"]) == {
        "AAPL",
        "MSFT",
    }


def test_rejects_empty_prices():
    with pytest.raises(
        ValueError,
        match="prices",
    ):
        build_portfolio_inputs_from_prices(
            pd.DataFrame()
        )


def test_rejects_insufficient_history():
    prices = pd.DataFrame(
        {
            "AAPL": [100.0],
        }
    )

    with pytest.raises(
        ValueError,
        match="historial",
    ):
        build_portfolio_inputs_from_prices(
            prices
        )
