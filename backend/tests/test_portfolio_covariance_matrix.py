import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)


def build_correlation_matrix():
    return PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4],
            "B": [2, 4, 6, 8],
            "C": [4, 3, 2, 1],
        }
    )


def test_covariance_matrix_calculates_diagonal_variances():
    matrix = PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_correlation_matrix(),
    )

    assert matrix.covariance("A", "A") == pytest.approx(
        0.04,
        abs=1e-6,
    )
    assert matrix.covariance("B", "B") == pytest.approx(
        0.01,
        abs=1e-6,
    )
    assert matrix.covariance("C", "C") == pytest.approx(
        0.0225,
        abs=1e-6,
    )


def test_covariance_matrix_uses_correlations():
    matrix = PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_correlation_matrix(),
    )

    assert matrix.covariance("A", "B") == pytest.approx(
        0.02,
        abs=1e-6,
    )

    assert matrix.covariance("A", "C") == pytest.approx(
        -0.03,
        abs=1e-6,
    )


def test_covariance_matrix_is_symmetric():
    matrix = PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_correlation_matrix(),
    )

    assert matrix.covariance(
        "A",
        "C",
    ) == pytest.approx(
        matrix.covariance(
            "C",
            "A",
        )
    )


def test_covariance_matrix_preserves_assets():
    matrix = PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_correlation_matrix(),
    )

    assert matrix.assets == (
        "A",
        "B",
        "C",
    )


def test_covariance_matrix_rejects_empty_volatilities():
    with pytest.raises(
        ValueError,
        match="volatilities",
    ):
        PortfolioCovarianceMatrix.from_inputs(
            volatilities={},
            correlation_matrix=build_correlation_matrix(),
        )


def test_covariance_matrix_rejects_missing_assets():
    with pytest.raises(
        ValueError,
        match="activos",
    ):
        PortfolioCovarianceMatrix.from_inputs(
            volatilities={
                "A": 0.20,
                "B": 0.10,
            },
            correlation_matrix=build_correlation_matrix(),
        )


def test_covariance_matrix_rejects_negative_volatility():
    with pytest.raises(
        ValueError,
        match="volatilidad",
    ):
        PortfolioCovarianceMatrix.from_inputs(
            volatilities={
                "A": 0.20,
                "B": -0.10,
                "C": 0.15,
            },
            correlation_matrix=build_correlation_matrix(),
        )


def test_covariance_matrix_rejects_invalid_correlation_matrix():
    with pytest.raises(
        TypeError,
        match="PortfolioCorrelationMatrix",
    ):
        PortfolioCovarianceMatrix.from_inputs(
            volatilities={
                "A": 0.20,
            },
            correlation_matrix=object(),
        )


def test_covariance_matrix_is_immutable():
    matrix = PortfolioCovarianceMatrix.from_inputs(
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_correlation_matrix(),
    )

    with pytest.raises(
        AttributeError,
    ):
        matrix.assets = ()
