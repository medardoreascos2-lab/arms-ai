import pytest

from backend.portfolio.portfolio_sortino_ratio_report import (
    PortfolioSortinoRatioReport,
)


def test_sortino_report_calculates_ratio():
    report = PortfolioSortinoRatioReport.from_returns(
        returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
        ],
        risk_free_rate=0.02,
        periods_per_year=252,
    )

    assert report.sortino_ratio > 0.0

    assert report.excess_return == pytest.approx(
        report.annualized_return
        - report.risk_free_rate,
        abs=1e-6,
    )


def test_sortino_report_uses_downside_deviation():
    report = PortfolioSortinoRatioReport.from_returns(
        returns=[
            0.02,
            -0.01,
            -0.03,
            0.01,
        ],
        periods_per_year=252,
    )

    assert report.downside_deviation > 0.0


def test_sortino_report_handles_zero_downside_deviation():
    report = PortfolioSortinoRatioReport.from_returns(
        returns=[
            0.02,
            0.03,
            0.01,
        ],
        periods_per_year=252,
    )

    assert report.downside_deviation == 0.0
    assert report.sortino_ratio == 0.0


@pytest.mark.parametrize(
    "periods_per_year",
    [0, -1],
)
def test_sortino_report_rejects_invalid_periods(
    periods_per_year,
):
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioSortinoRatioReport.from_returns(
            returns=[0.01, 0.02],
            periods_per_year=periods_per_year,
        )


def test_sortino_report_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioSortinoRatioReport.from_returns(
            returns=[],
        )


def test_sortino_report_is_immutable():
    report = PortfolioSortinoRatioReport.from_returns(
        returns=[
            0.01,
            0.02,
        ],
    )

    with pytest.raises(
        AttributeError,
    ):
        report.sortino_ratio = 0.0
