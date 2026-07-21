import pytest

from backend.portfolio.stress_testing import (
    StressTesting,
)


def test_applies_asset_shocks():
    result = StressTesting().calculate(
        weights={
            "AAPL": 0.6,
            "MSFT": 0.4,
        },
        shocks={
            "AAPL": -0.30,
            "MSFT": -0.10,
        },
        initial_value=1000.0,
    )

    assert result["final_value"] == pytest.approx(
        780.0
    )
    assert result["absolute_loss"] == pytest.approx(
        -220.0
    )
    assert result["percentage_loss"] == pytest.approx(
        -0.22
    )


def test_returns_asset_impacts():
    result = StressTesting().calculate(
        weights={
            "AAPL": 0.6,
            "MSFT": 0.4,
        },
        shocks={
            "AAPL": -0.30,
            "MSFT": -0.10,
        },
        initial_value=1000.0,
    )

    assert result["asset_impacts"]["AAPL"] == pytest.approx(
        -180.0
    )
    assert result["asset_impacts"]["MSFT"] == pytest.approx(
        -40.0
    )


def test_identifies_worst_and_best_assets():
    result = StressTesting().calculate(
        weights={
            "AAPL": 0.6,
            "MSFT": 0.4,
        },
        shocks={
            "AAPL": -0.30,
            "MSFT": -0.10,
        },
    )

    assert result["worst_asset"] == "AAPL"
    assert result["best_asset"] == "MSFT"


def test_rejects_invalid_weights():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        StressTesting().calculate(
            weights={
                "AAPL": 0.2,
                "MSFT": 0.2,
            },
            shocks={
                "AAPL": -0.30,
                "MSFT": -0.10,
            },
        )


def test_rejects_missing_shocks():
    with pytest.raises(
        ValueError,
        match="shocks",
    ):
        StressTesting().calculate(
            weights={
                "AAPL": 0.6,
                "MSFT": 0.4,
            },
            shocks={
                "AAPL": -0.30,
            },
        )


def test_rejects_non_positive_initial_value():
    with pytest.raises(
        ValueError,
        match="initial_value",
    ):
        StressTesting().calculate(
            weights={
                "AAPL": 1.0,
            },
            shocks={
                "AAPL": -0.20,
            },
            initial_value=0.0,
        )
