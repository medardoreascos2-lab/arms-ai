import pytest

from backend.portfolio.portfolio_information_ratio_report import (
    PortfolioInformationRatioReport,
)


def test_information_ratio_calculates_active_return():
    report = PortfolioInformationRatioReport.from_returns(
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
        periods_per_year=252,
    )

    assert report.mean_active_return == pytest.approx(
        0.01,
        abs=1e-6,
    )

    assert report.annualized_active_return == pytest.approx(
        2.52,
        abs=1e-6,
    )


def test_information_ratio_calculates_tracking_error():
    report = PortfolioInformationRatioReport.from_returns(
        portfolio_returns=[
            0.02,
            0.01,
            0.03,
            -0.01,
        ],
        benchmark_returns=[
            0.01,
            0.02,
            0.01,
            -0.02,
        ],
        periods_per_year=252,
    )

    assert report.tracking_error > 0.0
    assert report.annualized_tracking_error > 0.0


def test_information_ratio_calculates_ratio():
    report = PortfolioInformationRatioReport.from_returns(
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

    assert report.information_ratio > 0.0

    assert report.information_ratio == pytest.approx(
        report.annualized_active_return
        / report.annualized_tracking_error,
        abs=1e-6,
    )


def test_information_ratio_handles_zero_tracking_error():
    report = PortfolioInformationRatioReport.from_returns(
        portfolio_returns=[
            0.02,
            0.03,
            0.01,
        ],
        benchmark_returns=[
            0.01,
            0.02,
            0.00,
        ],
        periods_per_year=252,
    )

    assert report.tracking_error == 0.0
    assert report.information_ratio == 0.0


def test_information_ratio_preserves_sample_size():
    report = PortfolioInformationRatioReport.from_returns(
        portfolio_returns=[
            0.01,
            0.02,
            0.03,
        ],
        benchmark_returns=[
            0.00,
            0.01,
            0.02,
        ],
    )

    assert report.sample_size == 3


def test_information_ratio_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioInformationRatioReport.from_returns(
            portfolio_returns=[],
            benchmark_returns=[],
        )


def test_information_ratio_rejects_different_lengths():
    with pytest.raises(
        ValueError,
        match="length",
    ):
        PortfolioInformationRatioReport.from_returns(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.01,
            ],
        )


def test_information_ratio_rejects_single_observation():
    with pytest.raises(
        ValueError,
        match="al menos 2",
    ):
        PortfolioInformationRatioReport.from_returns(
            portfolio_returns=[
                0.01,
            ],
            benchmark_returns=[
                0.00,
            ],
        )


def test_information_ratio_rejects_invalid_periods():
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioInformationRatioReport.from_returns(
            portfolio_returns=[
                0.01,
                0.02,
            ],
            benchmark_returns=[
                0.00,
                0.01,
            ],
            periods_per_year=0,
        )


def test_information_ratio_is_immutable():
    report = PortfolioInformationRatioReport.from_returns(
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
        report.information_ratio = 0.0
