import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_volatility_report import (
    PortfolioVolatilityReport,
)


def build_matrix() -> PortfolioCorrelationMatrix:
    return PortfolioCorrelationMatrix.from_returns(
        {
            "A": [0.01, 0.02, -0.01, 0.03],
            "B": [0.02, 0.01, 0.00, 0.02],
            "C": [-0.01, -0.02, 0.01, -0.03],
        }
    )


def test_volatility_report_calculates_portfolio_volatility():
    report = PortfolioVolatilityReport.from_inputs(
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

    assert report.portfolio_volatility >= 0.0


def test_volatility_report_calculates_annualized_volatility():
    report = PortfolioVolatilityReport.from_inputs(
        weights={
            "A": 60.0,
            "B": 40.0,
        },
        volatilities={
            "A": 0.02,
            "B": 0.01,
        },
        correlation_matrix=PortfolioCorrelationMatrix.from_returns(
            {
                "A": [1, 2, 3, 4],
                "B": [1, 2, 3, 4],
            }
        ),
        periods_per_year=252,
    )

    assert report.annualized_volatility == pytest.approx(
        report.portfolio_volatility
        * 252 ** 0.5,
        abs=1e-6,
    )


def test_volatility_report_detects_extreme_assets():
    report = PortfolioVolatilityReport.from_inputs(
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

    assert report.most_volatile_asset == "A"
    assert report.least_volatile_asset == "B"


def test_volatility_report_preserves_asset_volatilities():
    report = PortfolioVolatilityReport.from_inputs(
        weights={
            "A": 50.0,
            "B": 50.0,
        },
        volatilities={
            "A": 0.20,
            "B": 0.10,
        },
        correlation_matrix=PortfolioCorrelationMatrix.from_returns(
            {
                "A": [1, 2, 3],
                "B": [1, 2, 3],
            }
        ),
    )

    assert report.asset_volatilities["A"] == 0.20
    assert report.asset_volatilities["B"] == 0.10


def test_volatility_report_rejects_empty_weights():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        PortfolioVolatilityReport.from_inputs(
            weights={},
            volatilities={},
            correlation_matrix=build_matrix(),
        )


def test_volatility_report_rejects_mismatched_assets():
    with pytest.raises(
        ValueError,
        match="activos",
    ):
        PortfolioVolatilityReport.from_inputs(
            weights={
                "A": 100.0,
            },
            volatilities={
                "B": 0.20,
            },
            correlation_matrix=build_matrix(),
        )


def test_volatility_report_rejects_invalid_periods():
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioVolatilityReport.from_inputs(
            weights={
                "A": 100.0,
            },
            volatilities={
                "A": 0.20,
            },
            correlation_matrix=PortfolioCorrelationMatrix.from_returns(
                {
                    "A": [1, 2],
                }
            ),
            periods_per_year=0,
        )


def test_volatility_report_is_immutable():
    report = PortfolioVolatilityReport.from_inputs(
        weights={
            "A": 100.0,
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
        report.portfolio_volatility = 0.0
