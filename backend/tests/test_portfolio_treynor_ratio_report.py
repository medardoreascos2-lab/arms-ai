import pytest

from backend.portfolio.portfolio_treynor_ratio_report import (
    PortfolioTreynorRatioReport,
)


def test_treynor_report_calculates_ratio():
    report = PortfolioTreynorRatioReport.from_returns(
        portfolio_returns=[
            0.02,
            0.01,
            0.03,
            -0.01,
        ],
        benchmark_returns=[
            0.01,
            0.00,
            0.02,
            -0.02,
        ],
        risk_free_rate=0.02,
        periods_per_year=252,
    )

    assert report.treynor_ratio > 0.0

    assert report.excess_return == pytest.approx(
        report.annualized_return
        - report.risk_free_rate,
        abs=1e-6,
    )


def test_treynor_report_preserves_beta():
    report = PortfolioTreynorRatioReport.from_returns(
        portfolio_returns=[
            0.03,
            0.02,
            0.04,
            0.01,
        ],
        benchmark_returns=[
            0.01,
            0.02,
            0.01,
            0.00,
        ],
        periods_per_year=252,
    )

    assert report.beta > 0.0
    assert report.classification in {
        "Defensive",
        "Neutral",
        "Aggressive",
    }


def test_treynor_report_handles_zero_beta():
    report = PortfolioTreynorRatioReport.from_returns(
        portfolio_returns=[
            0.01,
            0.02,
            0.03,
        ],
        benchmark_returns=[
            0.01,
            0.01,
            0.01,
        ],
        periods_per_year=252,
    )

    assert report.beta == 0.0
    assert report.treynor_ratio == 0.0


def test_treynor_report_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioTreynorRatioReport.from_returns(
            portfolio_returns=[],
            benchmark_returns=[],
        )


def test_treynor_report_rejects_different_lengths():
    with pytest.raises(
        ValueError,
        match="length",
    ):
        PortfolioTreynorRatioReport.from_returns(
            portfolio_returns=[0.01],
            benchmark_returns=[0.01, 0.02],
        )


def test_treynor_report_rejects_invalid_periods():
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioTreynorRatioReport.from_returns(
            portfolio_returns=[0.01, 0.02],
            benchmark_returns=[0.00, 0.01],
            periods_per_year=0,
        )


def test_treynor_report_is_immutable():
    report = PortfolioTreynorRatioReport.from_returns(
        portfolio_returns=[
            0.01,
            0.02,
        ],
        benchmark_returns=[
            0.00,
            0.01,
        ],
    )

    with pytest.raises(
        AttributeError,
    ):
        report.treynor_ratio = 0.0
