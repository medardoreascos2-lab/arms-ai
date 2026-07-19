import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_maximum_sharpe_optimizer import (
    PortfolioMaximumSharpeOptimizer,
)


def build_covariance_matrix():
    correlation = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4],
            "B": [1, 2, 3, 4],
            "C": [1, 2, 3, 4],
        }
    )

    return PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.10,
            "B": 0.20,
            "C": 0.30,
        },
        correlation_matrix=correlation,
    )


def build_expected_returns():
    return {
        "A": 0.08,
        "B": 0.12,
        "C": 0.18,
    }


def test_optimizer_returns_weights():
    result = PortfolioMaximumSharpeOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert set(result.weights) == {
        "A",
        "B",
        "C",
    }


def test_optimizer_weights_sum_to_one_hundred():
    result = PortfolioMaximumSharpeOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert sum(result.weights.values()) == pytest.approx(
        100.0,
        abs=0.01,
    )


def test_optimizer_calculates_sharpe():
    result = PortfolioMaximumSharpeOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
        risk_free_rate=0.02,
    )

    assert result.sharpe_ratio > 0.0


def test_optimizer_preserves_assets():
    result = PortfolioMaximumSharpeOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert result.assets == (
        "A",
        "B",
        "C",
    )


def test_optimizer_rejects_invalid_matrix():
    with pytest.raises(
        TypeError,
        match="PortfolioCovarianceMatrix",
    ):
        PortfolioMaximumSharpeOptimizer.optimize(
            covariance_matrix=object(),
            expected_returns=build_expected_returns(),
        )


def test_optimizer_rejects_missing_returns():
    with pytest.raises(
        ValueError,
        match="expected_returns",
    ):
        PortfolioMaximumSharpeOptimizer.optimize(
            covariance_matrix=build_covariance_matrix(),
            expected_returns={},
        )


def test_optimizer_is_immutable():
    result = PortfolioMaximumSharpeOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    with pytest.raises(
        AttributeError,
    ):
        result.sharpe_ratio = 0.0
