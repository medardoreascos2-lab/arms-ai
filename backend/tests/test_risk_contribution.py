import numpy as np
import pytest

from backend.portfolio.risk_contribution import (
    RiskContribution,
)


def build_covariance() -> np.ndarray:
    return np.array(
        [
            [0.0400, 0.0120, 0.0180],
            [0.0120, 0.0324, 0.0105],
            [0.0180, 0.0105, 0.1225],
        ],
        dtype=float,
    )


def build_weights() -> dict[str, float]:
    return {
        "AAPL": 0.40,
        "MSFT": 0.35,
        "NVDA": 0.25,
    }


def test_returns_risk_contribution_metrics():
    result = RiskContribution().calculate(
        covariance_matrix=build_covariance(),
        weights=build_weights(),
    )

    assert "portfolio_volatility" in result
    assert "marginal_contributions" in result
    assert "absolute_contributions" in result
    assert "percentage_contributions" in result
    assert "highest_risk_asset" in result
    assert "lowest_risk_asset" in result


def test_percentage_contributions_sum_to_one():
    result = RiskContribution().calculate(
        covariance_matrix=build_covariance(),
        weights=build_weights(),
    )

    assert sum(
        result["percentage_contributions"].values()
    ) == pytest.approx(
        1.0
    )


def test_absolute_contributions_sum_to_volatility():
    result = RiskContribution().calculate(
        covariance_matrix=build_covariance(),
        weights=build_weights(),
    )

    assert sum(
        result["absolute_contributions"].values()
    ) == pytest.approx(
        result["portfolio_volatility"]
    )


def test_rejects_invalid_weights():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        RiskContribution().calculate(
            covariance_matrix=build_covariance(),
            weights={
                "AAPL": 0.20,
                "MSFT": 0.20,
                "NVDA": 0.20,
            },
        )


def test_rejects_covariance_shape_mismatch():
    with pytest.raises(
        ValueError,
        match="covariance_matrix",
    ):
        RiskContribution().calculate(
            covariance_matrix=np.eye(2),
            weights=build_weights(),
        )


def test_rejects_zero_portfolio_risk():
    with pytest.raises(
        ValueError,
        match="portfolio",
    ):
        RiskContribution().calculate(
            covariance_matrix=np.zeros(
                (3, 3)
            ),
            weights=build_weights(),
        )
