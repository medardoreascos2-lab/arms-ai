import pytest

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_exposure_report import (
    PortfolioExposureReport,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)


def build_portfolio():
    return Portfolio(
        positions=[
            PortfolioPosition(
                symbol="NQ",
                quantity=2,
                average_price=100,
                current_price=110,
            ),
            PortfolioPosition(
                symbol="ES",
                quantity=-3,
                average_price=50,
                current_price=40,
            ),
            PortfolioPosition(
                symbol="CL",
                quantity=1,
                average_price=70,
                current_price=75,
            ),
        ]
    )


def test_exposure_report_calculates_totals():
    report = PortfolioExposureReport.from_portfolio(
        build_portfolio()
    )

    assert report.long_exposure == 295.0
    assert report.short_exposure == 120.0
    assert report.gross_exposure == 415.0
    assert report.net_exposure == 175.0


def test_exposure_report_calculates_percentages():
    report = PortfolioExposureReport.from_portfolio(
        build_portfolio()
    )

    assert report.long_percent == pytest.approx(
        71.08,
        abs=0.01,
    )

    assert report.short_percent == pytest.approx(
        28.92,
        abs=0.01,
    )

    assert report.net_percent == pytest.approx(
        42.17,
        abs=0.01,
    )


def test_exposure_report_empty_portfolio():
    report = PortfolioExposureReport.from_portfolio(
        Portfolio(
            positions=[],
        )
    )

    assert report.long_exposure == 0.0
    assert report.short_exposure == 0.0
    assert report.gross_exposure == 0.0
    assert report.net_exposure == 0.0

    assert report.long_percent == 0.0
    assert report.short_percent == 0.0
    assert report.net_percent == 0.0


def test_exposure_report_rejects_invalid_portfolio():
    with pytest.raises(
        TypeError,
        match="Portfolio",
    ):
        PortfolioExposureReport.from_portfolio(
            object(),
        )


def test_exposure_report_is_immutable():
    report = PortfolioExposureReport.from_portfolio(
        build_portfolio()
    )

    with pytest.raises(
        AttributeError,
    ):
        report.long_exposure = 0
