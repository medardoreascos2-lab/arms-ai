import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_minimum_variance_optimizer import (
    PortfolioMinimumVarianceOptimizer,
)


def build_covariance_matrix():
    correlation_matrix = (
        PortfolioCorrelationMatrix.from_returns(
            {
                "A": [1, 2, 3, 4],
                "B": [1, 2, 3, 4],
                "C": [1, 2, 3, 4],
            }
        )
    )

    return PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.10,
            "B": 0.20,
            "C": 0.40,
        },
        correlation_matrix=correlation_matrix,
    )


def test_optimizer_calculates_weights():
    result = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert set(result.weights) == {
        "A",
        "B",
        "C",
    }

    assert result.weights["A"] > result.weights["B"]
    assert result.weights["B"] > result.weights["C"]


def test_optimizer_weights_sum_to_one_hundred():
    result = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert sum(
        result.weights.values()
    ) == pytest.approx(
        100.0,
        abs=0.01,
    )


def test_optimizer_does_not_create_negative_weights():
    result = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert all(
        weight >= 0.0
        for weight in result.weights.values()
    )


def test_optimizer_calculates_portfolio_variance():
    result = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert result.portfolio_variance >= 0.0
    assert result.portfolio_volatility >= 0.0


def test_optimizer_preserves_asset_order():
    result = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert result.assets == (
        "A",
        "B",
        "C",
    )


def test_optimizer_is_deterministic():
    covariance_matrix = build_covariance_matrix()

    first = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=covariance_matrix,
    )
    second = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=covariance_matrix,
    )

    assert first.weights == second.weights
    assert (
        first.portfolio_variance
        == second.portfolio_variance
    )


def test_optimizer_handles_single_asset():
    correlation_matrix = (
        PortfolioCorrelationMatrix.from_returns(
            {
                "A": [1, 2, 3],
            }
        )
    )

    covariance_matrix = (
        PortfolioCovarianceMatrix.from_inputs(
            volatilities={
                "A": 0.20,
            },
            correlation_matrix=correlation_matrix,
        )
    )

    result = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=covariance_matrix,
    )

    assert result.weights["A"] == 100.0
    assert result.portfolio_variance == pytest.approx(
        0.04,
        abs=1e-6,
    )


def test_optimizer_rejects_invalid_covariance_matrix():
    with pytest.raises(
        TypeError,
        match="PortfolioCovarianceMatrix",
    ):
        PortfolioMinimumVarianceOptimizer.optimize(
            covariance_matrix=object(),
        )


def test_optimizer_is_immutable():
    result = PortfolioMinimumVarianceOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    with pytest.raises(
        AttributeError,
    ):
        result.portfolio_variance = 0.0
