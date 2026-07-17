import pytest

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_concentration_report import (
    PortfolioConcentrationReport,
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


def test_concentration_report_calculates_top_holdings():
    report = PortfolioConcentrationReport.from_portfolio(
        build_portfolio()
    )

    assert report.top_1_weight == pytest.approx(
        53.01,
        abs=0.01,
    )

    assert report.top_2_weight == pytest.approx(
        81.93,
        abs=0.01,
    )

    assert report.top_3_weight == 100.0


def test_concentration_report_calculates_hhi():
    report = PortfolioConcentrationReport.from_portfolio(
        build_portfolio()
    )

    assert report.herfindahl_index == pytest.approx(
        0.395,
        abs=0.005,
    )


def test_concentration_report_calculates_effective_positions():
    report = PortfolioConcentrationReport.from_portfolio(
        build_portfolio()
    )

    assert report.effective_positions == pytest.approx(
        2.53,
        abs=0.05,
    )


def test_concentration_report_classifies_risk():
    report = PortfolioConcentrationReport.from_portfolio(
        build_portfolio()
    )

    assert report.risk_level in (
        "low",
        "moderate",
        "high",
    )


def test_concentration_report_empty_portfolio():
    report = PortfolioConcentrationReport.from_portfolio(
        Portfolio(
            positions=[],
        )
    )

    assert report.top_1_weight == 0.0
    assert report.top_2_weight == 0.0
    assert report.top_3_weight == 0.0
    assert report.herfindahl_index == 0.0
    assert report.effective_positions == 0.0
    assert report.risk_level == "none"


def test_concentration_report_rejects_invalid_portfolio():
    with pytest.raises(
        TypeError,
        match="Portfolio",
    ):
        PortfolioConcentrationReport.from_portfolio(
            object(),
        )


def test_concentration_report_is_immutable():
    report = PortfolioConcentrationReport.from_portfolio(
        build_portfolio()
    )

    with pytest.raises(
        AttributeError,
    ):
        report.top_1_weight = 0
