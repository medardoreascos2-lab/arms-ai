import pytest

from backend.portfolio.portfolio_tracking_error_report import (
    PortfolioTrackingErrorReport,
)


def test_tracking_error_calculates_active_returns():
    report = PortfolioTrackingErrorReport.from_returns(
        portfolio_returns=[
            0.02, 0.01, 0.03, -0.01,
        ],
        benchmark_returns=[
            0.01, 0.00, 0.02, -0.02,
        ],
    )

    assert report.mean_active_return == pytest.approx(
        0.01,
        abs=1e-6,
    )


def test_tracking_error_calculates_tracking_error():
    report = PortfolioTrackingErrorReport.from_returns(
        portfolio_returns=[
            0.02, 0.01, 0.03, -0.01,
        ],
        benchmark_returns=[
            0.01, 0.02, 0.01, -0.02,
        ],
        periods_per_year=252,
    )

    assert report.tracking_error > 0
    assert report.annualized_tracking_error > 0


def test_tracking_error_handles_identical_returns():
    report = PortfolioTrackingErrorReport.from_returns(
        portfolio_returns=[
            0.01, 0.02, 0.03,
        ],
        benchmark_returns=[
            0.01, 0.02, 0.03,
        ],
    )

    assert report.tracking_error == 0.0
    assert report.annualized_tracking_error == 0.0


def test_tracking_error_preserves_sample_size():
    report = PortfolioTrackingErrorReport.from_returns(
        portfolio_returns=[
            0.01, 0.02, 0.03,
        ],
        benchmark_returns=[
            0.00, 0.01, 0.02,
        ],
    )

    assert report.sample_size == 3


def test_tracking_error_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioTrackingErrorReport.from_returns(
            portfolio_returns=[],
            benchmark_returns=[],
        )


def test_tracking_error_rejects_different_lengths():
    with pytest.raises(
        ValueError,
        match="length",
    ):
        PortfolioTrackingErrorReport.from_returns(
            portfolio_returns=[0.01],
            benchmark_returns=[0.01, 0.02],
        )


def test_tracking_error_rejects_single_observation():
    with pytest.raises(
        ValueError,
        match="al menos 2",
    ):
        PortfolioTrackingErrorReport.from_returns(
            portfolio_returns=[0.01],
            benchmark_returns=[0.00],
        )


def test_tracking_error_rejects_invalid_periods():
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioTrackingErrorReport.from_returns(
            portfolio_returns=[0.01, 0.02],
            benchmark_returns=[0.00, 0.01],
            periods_per_year=0,
        )


def test_tracking_error_is_immutable():
    report = PortfolioTrackingErrorReport.from_returns(
        portfolio_returns=[0.01, 0.02],
        benchmark_returns=[0.00, 0.01],
    )

    with pytest.raises(
        AttributeError,
    ):
        report.tracking_error = 0.0
