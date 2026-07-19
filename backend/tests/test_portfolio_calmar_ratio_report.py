import pytest

from backend.portfolio.portfolio_calmar_ratio_report import (
    PortfolioCalmarRatioReport,
)


def test_calmar_report_calculates_ratio():
    report = PortfolioCalmarRatioReport.from_equity_curve(
        equity_curve=[
            1000.0,
            1100.0,
            1050.0,
            1200.0,
        ],
        periods_per_year=252,
    )

    assert report.annualized_return > 0.0
    assert report.max_drawdown > 0.0
    assert report.calmar_ratio > 0.0


def test_calmar_report_calculates_max_drawdown():
    report = PortfolioCalmarRatioReport.from_equity_curve(
        equity_curve=[
            1000.0,
            1200.0,
            900.0,
            1100.0,
        ],
    )

    assert report.max_drawdown == pytest.approx(
        0.25,
        abs=1e-6,
    )


def test_calmar_report_handles_zero_drawdown():
    report = PortfolioCalmarRatioReport.from_equity_curve(
        equity_curve=[
            1000.0,
            1100.0,
            1200.0,
        ],
    )

    assert report.max_drawdown == 0.0
    assert report.calmar_ratio == 0.0


def test_calmar_report_preserves_sample_size():
    report = PortfolioCalmarRatioReport.from_equity_curve(
        equity_curve=[
            1000.0,
            1050.0,
            1100.0,
        ],
    )

    assert report.sample_size == 3


def test_calmar_report_rejects_empty_equity_curve():
    with pytest.raises(
        ValueError,
        match="equity_curve",
    ):
        PortfolioCalmarRatioReport.from_equity_curve(
            equity_curve=[],
        )


def test_calmar_report_rejects_single_value():
    with pytest.raises(
        ValueError,
        match="al menos 2",
    ):
        PortfolioCalmarRatioReport.from_equity_curve(
            equity_curve=[
                1000.0,
            ],
        )


def test_calmar_report_rejects_non_positive_equity():
    with pytest.raises(
        ValueError,
        match="equity",
    ):
        PortfolioCalmarRatioReport.from_equity_curve(
            equity_curve=[
                1000.0,
                0.0,
            ],
        )


def test_calmar_report_rejects_invalid_periods():
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioCalmarRatioReport.from_equity_curve(
            equity_curve=[
                1000.0,
                1100.0,
            ],
            periods_per_year=0,
        )


def test_calmar_report_is_immutable():
    report = PortfolioCalmarRatioReport.from_equity_curve(
        equity_curve=[
            1000.0,
            1100.0,
        ],
    )

    with pytest.raises(
        AttributeError,
    ):
        report.calmar_ratio = 0.0
