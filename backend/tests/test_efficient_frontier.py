import numpy as np

from backend.portfolio.efficient_frontier import (
    EfficientFrontier,
)


def test_generates_requested_number_of_portfolios():
    covariance = np.array([
        [0.10, 0.02],
        [0.02, 0.08],
    ])

    expected_returns = {
        "A": 0.10,
        "B": 0.15,
    }

    frontier = EfficientFrontier()

    portfolios = frontier.generate(
        covariance_matrix=covariance,
        expected_returns=expected_returns,
        portfolios=250,
        seed=42,
    )

    assert len(portfolios) == 250


def test_weights_sum_to_one():
    covariance = np.array([
        [0.10, 0.02],
        [0.02, 0.08],
    ])

    expected_returns = {
        "A": 0.10,
        "B": 0.15,
    }

    frontier = EfficientFrontier()

    portfolios = frontier.generate(
        covariance_matrix=covariance,
        expected_returns=expected_returns,
        portfolios=100,
        seed=42,
    )

    for portfolio in portfolios:
        assert abs(sum(portfolio["weights"].values()) - 1.0) < 1e-9


def test_contains_return_and_volatility():
    covariance = np.array([
        [0.10, 0.02],
        [0.02, 0.08],
    ])

    expected_returns = {
        "A": 0.10,
        "B": 0.15,
    }

    frontier = EfficientFrontier()

    portfolio = frontier.generate(
        covariance_matrix=covariance,
        expected_returns=expected_returns,
        portfolios=1,
        seed=42,
    )[0]

    assert "expected_return" in portfolio
    assert "volatility" in portfolio
    assert "weights" in portfolio
