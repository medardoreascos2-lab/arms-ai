import pytest

from backend.portfolio.portfolio_sharpe_ratio_report import (
    PortfolioSharpeRatioReport,
)


def test_sharpe_report_calculates_ratio():
    report = PortfolioSharpeRatioReport.from_returns(
        returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
        ],
        risk_free_rate=0.02,
        periods_per_year=252,
    )

    assert report.sharpe_ratio > 0.0

    assert report.excess_return == pytest.approx(
        report.annualized_return
        - report.risk_free_rate,
        abs=1e-6,
    )


def test_sharpe_report_preserves_statistics():
    report = PortfolioSharpeRatioReport.from_returns(
        returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
        ],
        periods_per_year=252,
    )

    assert report.sample_size == 4
    assert report.periods_per_year == 252
    assert report.annualized_volatility > 0.0


def test_sharpe_report_handles_zero_volatility():
    report = PortfolioSharpeRatioReport.from_returns(
        returns=[
            0.01,
            0.01,
            0.01,
        ],
        periods_per_year=252,
    )

    assert report.annualized_volatility == 0.0
    assert report.sharpe_ratio == 0.0


@pytest.mark.parametrize(
    "periods_per_year",
    [0, -1],
)
def test_sharpe_report_rejects_invalid_periods(
    periods_per_year,
):
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioSharpeRatioReport.from_returns(
            returns=[
                0.01,
                0.02,
            ],
            periods_per_year=periods_per_year,
        )


def test_sharpe_report_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioSharpeRatioReport.from_returns(
            returns=[],
        )


def test_sharpe_report_rejects_single_return():
    with pytest.raises(
        ValueError,
        match="al menos 2",
    ):
        PortfolioSharpeRatioReport.from_returns(
            returns=[
                0.01,
            ],
        )


def test_sharpe_report_is_immutable():
    report = PortfolioSharpeRatioReport.from_returns(
        returns=[
            0.01,
            0.02,
        ],
    )

    with pytest.raises(
        AttributeError,
    ):
        report.sharpe_ratio = 0.0
