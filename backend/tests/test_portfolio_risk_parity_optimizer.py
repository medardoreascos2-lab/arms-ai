import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_risk_parity_optimizer import (
    PortfolioRiskParityOptimizer,
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
            "C": 0.40,
        },
        correlation_matrix=correlation,
    )


def test_optimizer_calculates_weights():
    result = PortfolioRiskParityOptimizer.optimize(
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
    result = PortfolioRiskParityOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert sum(
        result.weights.values()
    ) == pytest.approx(
        100.0,
        abs=0.01,
    )


def test_optimizer_calculates_risk_contributions():
    result = PortfolioRiskParityOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert set(result.risk_contributions) == {
        "A",
        "B",
        "C",
    }

    assert sum(
        result.risk_contributions.values()
    ) == pytest.approx(
        100.0,
        abs=0.01,
    )


def test_optimizer_calculates_portfolio_risk():
    result = PortfolioRiskParityOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert result.portfolio_variance >= 0.0
    assert result.portfolio_volatility >= 0.0


def test_optimizer_preserves_assets():
    result = PortfolioRiskParityOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    assert result.assets == (
        "A",
        "B",
        "C",
    )


def test_optimizer_is_deterministic():
    covariance_matrix = build_covariance_matrix()

    first = PortfolioRiskParityOptimizer.optimize(
        covariance_matrix=covariance_matrix,
    )
    second = PortfolioRiskParityOptimizer.optimize(
        covariance_matrix=covariance_matrix,
    )

    assert first.weights == second.weights
    assert (
        first.risk_contributions
        == second.risk_contributions
    )


def test_optimizer_rejects_invalid_matrix():
    with pytest.raises(
        TypeError,
        match="PortfolioCovarianceMatrix",
    ):
        PortfolioRiskParityOptimizer.optimize(
            covariance_matrix=object(),
        )


def test_optimizer_is_immutable():
    result = PortfolioRiskParityOptimizer.optimize(
        covariance_matrix=build_covariance_matrix(),
    )

    with pytest.raises(
        AttributeError,
    ):
        result.portfolio_variance = 0.0
