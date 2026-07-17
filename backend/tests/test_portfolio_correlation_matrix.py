import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)


def test_correlation_matrix_builds_identity():
    matrix = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [0.01, 0.02, 0.03],
            "B": [0.01, 0.02, 0.03],
        }
    )

    assert matrix.correlation("A", "A") == pytest.approx(1.0)
    assert matrix.correlation("B", "B") == pytest.approx(1.0)


def test_correlation_matrix_detects_positive_correlation():
    matrix = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4, 5],
            "B": [2, 4, 6, 8, 10],
        }
    )

    assert matrix.correlation("A", "B") == pytest.approx(
        1.0,
        abs=1e-6,
    )


def test_correlation_matrix_detects_negative_correlation():
    matrix = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4],
            "B": [4, 3, 2, 1],
        }
    )

    assert matrix.correlation("A", "B") == pytest.approx(
        -1.0,
        abs=1e-6,
    )


def test_correlation_matrix_is_symmetric():
    matrix = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3],
            "B": [2, 1, 0],
        }
    )

    assert matrix.correlation("A", "B") == pytest.approx(
        matrix.correlation("B", "A")
    )


def test_correlation_matrix_rejects_empty_data():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioCorrelationMatrix.from_returns(
            {}
        )


def test_correlation_matrix_rejects_different_lengths():
    with pytest.raises(
        ValueError,
        match="length",
    ):
        PortfolioCorrelationMatrix.from_returns(
            {
                "A": [1, 2],
                "B": [1],
            }
        )


def test_correlation_matrix_is_immutable():
    matrix = PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3],
            "B": [1, 2, 3],
        }
    )

    with pytest.raises(
        AttributeError,
    ):
        matrix.assets = ()
