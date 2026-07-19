import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_optimization_report import (
    PortfolioOptimizationReport,
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


def test_report_builds_all_strategies():
    report = PortfolioOptimizationReport.build(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert report.minimum_variance is not None
    assert report.maximum_sharpe is not None
    assert report.risk_parity is not None


def test_report_preserves_assets():
    report = PortfolioOptimizationReport.build(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert report.assets == (
        "A",
        "B",
        "C",
    )


def test_report_selects_best_strategy():
    report = PortfolioOptimizationReport.build(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    assert report.selected_strategy in {
        "minimum_variance",
        "maximum_sharpe",
        "risk_parity",
    }


def test_report_rejects_invalid_matrix():
    with pytest.raises(
        TypeError,
        match="PortfolioCovarianceMatrix",
    ):
        PortfolioOptimizationReport.build(
            covariance_matrix=object(),
            expected_returns=build_expected_returns(),
        )


def test_report_rejects_missing_returns():
    with pytest.raises(
        ValueError,
        match="expected_returns",
    ):
        PortfolioOptimizationReport.build(
            covariance_matrix=build_covariance_matrix(),
            expected_returns={},
        )


def test_report_is_immutable():
    report = PortfolioOptimizationReport.build(
        covariance_matrix=build_covariance_matrix(),
        expected_returns=build_expected_returns(),
    )

    with pytest.raises(
        AttributeError,
    ):
        report.selected_strategy = ""
