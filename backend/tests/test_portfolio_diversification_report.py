import pytest

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)
from backend.portfolio.portfolio_diversification_report import (
    PortfolioDiversificationReport,
)


def build_matrix():
    return PortfolioCorrelationMatrix.from_returns(
        {
            "A": [1, 2, 3, 4, 5],
            "B": [2, 4, 6, 8, 10],
            "C": [5, 4, 3, 2, 1],
        }
    )


def test_diversification_report_calculates_average_correlation():
    report = PortfolioDiversificationReport.from_matrix(
        build_matrix()
    )

    assert report.average_correlation == pytest.approx(
        -0.33,
        abs=0.05,
    )


def test_diversification_report_detects_extremes():
    report = PortfolioDiversificationReport.from_matrix(
        build_matrix()
    )

    assert report.max_correlation == pytest.approx(
        1.0,
        abs=1e-6,
    )

    assert report.min_correlation == pytest.approx(
        -1.0,
        abs=1e-6,
    )


def test_diversification_report_builds_score():
    report = PortfolioDiversificationReport.from_matrix(
        build_matrix()
    )

    assert 0 <= report.score <= 100


def test_diversification_report_classifies_level():
    report = PortfolioDiversificationReport.from_matrix(
        build_matrix()
    )

    assert report.level in (
        "poor",
        "fair",
        "good",
        "excellent",
    )


def test_diversification_report_rejects_invalid_matrix():
    with pytest.raises(
        TypeError,
        match="PortfolioCorrelationMatrix",
    ):
        PortfolioDiversificationReport.from_matrix(
            object(),
        )


def test_diversification_report_is_immutable():
    report = PortfolioDiversificationReport.from_matrix(
        build_matrix()
    )

    with pytest.raises(
        AttributeError,
    ):
        report.score = 0
