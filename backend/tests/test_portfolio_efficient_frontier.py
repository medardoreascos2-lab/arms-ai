import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_efficient_frontier import (
    PortfolioEfficientFrontier,
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


def test_frontier_generates_requested_points():
    frontier = PortfolioEfficientFrontier.generate(
        covariance_matrix=build_covariance_matrix(),
        points=25,
    )

    assert frontier.points == 25
    assert len(frontier.portfolios) == 25


def test_frontier_preserves_assets():
    frontier = PortfolioEfficientFrontier.generate(
        covariance_matrix=build_covariance_matrix(),
        points=10,
    )

    assert frontier.assets == (
        "A",
        "B",
        "C",
    )


def test_frontier_weights_sum_to_one_hundred():
    frontier = PortfolioEfficientFrontier.generate(
        covariance_matrix=build_covariance_matrix(),
        points=10,
    )

    for portfolio in frontier.portfolios:
        assert sum(
            portfolio.weights.values()
        ) == pytest.approx(
            100.0,
            abs=0.01,
        )


def test_frontier_is_deterministic():
    covariance = build_covariance_matrix()

    first = PortfolioEfficientFrontier.generate(
        covariance_matrix=covariance,
        points=15,
    )

    second = PortfolioEfficientFrontier.generate(
        covariance_matrix=covariance,
        points=15,
    )

    assert first.portfolios == second.portfolios


def test_frontier_rejects_invalid_points():
    with pytest.raises(
        ValueError,
        match="points",
    ):
        PortfolioEfficientFrontier.generate(
            covariance_matrix=build_covariance_matrix(),
            points=0,
        )


def test_frontier_rejects_invalid_matrix():
    with pytest.raises(
        TypeError,
        match="PortfolioCovarianceMatrix",
    ):
        PortfolioEfficientFrontier.generate(
            covariance_matrix=object(),
            points=10,
        )


def test_frontier_is_immutable():
    frontier = PortfolioEfficientFrontier.generate(
        covariance_matrix=build_covariance_matrix(),
        points=5,
    )

    with pytest.raises(
        AttributeError,
    ):
        frontier.points = 0
