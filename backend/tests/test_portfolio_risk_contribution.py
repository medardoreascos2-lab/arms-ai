import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_risk_contribution import (
    PortfolioRiskContribution,
)


def build_matrix():
    return PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4, 5],
            "B": [2, 4, 6, 8, 10],
            "C": [5, 4, 3, 2, 1],
        }
    )


def test_risk_contribution_normalizes_weights():
    report = PortfolioRiskContribution.from_inputs(
        weights={
            "A": 50.0,
            "B": 30.0,
            "C": 20.0,
        },
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_matrix(),
    )

    assert sum(
        report.contributions.values()
    ) == pytest.approx(
        100.0,
        abs=0.01,
    )


def test_highest_risk_asset_detected():
    report = PortfolioRiskContribution.from_inputs(
        weights={
            "A": 50,
            "B": 30,
            "C": 20,
        },
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_matrix(),
    )

    assert report.highest_risk_asset == "A"


def test_lowest_risk_asset_detected():
    report = PortfolioRiskContribution.from_inputs(
        weights={
            "A": 50,
            "B": 30,
            "C": 20,
        },
        volatilities={
            "A": 0.20,
            "B": 0.10,
            "C": 0.15,
        },
        correlation_matrix=build_matrix(),
    )

    assert report.lowest_risk_asset == "C"
    assert report.contributions["C"] < 0


def test_invalid_inputs_raise():
    with pytest.raises(
        ValueError,
    ):
        PortfolioRiskContribution.from_inputs(
            weights={},
            volatilities={},
            correlation_matrix=build_matrix(),
        )


def test_is_immutable():
    report = PortfolioRiskContribution.from_inputs(
        weights={
            "A": 100,
        },
        volatilities={
            "A": 0.20,
        },
        correlation_matrix=PortfolioCorrelationMatrix.from_returns(
            {
                "A": [1, 2],
            }
        ),
    )

    with pytest.raises(
        AttributeError,
    ):
        report.highest_risk_asset = "X"
