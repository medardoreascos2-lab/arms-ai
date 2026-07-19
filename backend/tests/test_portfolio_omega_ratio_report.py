import pytest

from backend.portfolio.portfolio_omega_ratio_report import (
    PortfolioOmegaRatioReport,
)


def test_omega_report_calculates_ratio():
    report = PortfolioOmegaRatioReport.from_returns(
        returns=[
            0.03,
            0.02,
            -0.01,
            -0.02,
        ],
        threshold=0.0,
    )

    assert report.omega_ratio == pytest.approx(
        5.0 / 3.0,
        abs=1e-6,
    )


def test_omega_report_calculates_gains_and_losses():
    report = PortfolioOmegaRatioReport.from_returns(
        returns=[
            0.03,
            0.01,
            -0.02,
            -0.01,
        ],
        threshold=0.0,
    )

    assert report.total_gains == pytest.approx(
        0.04,
        abs=1e-6,
    )
    assert report.total_losses == pytest.approx(
        0.03,
        abs=1e-6,
    )


def test_omega_report_supports_custom_threshold():
    report = PortfolioOmegaRatioReport.from_returns(
        returns=[
            0.03,
            0.02,
            0.00,
            -0.01,
        ],
        threshold=0.01,
    )

    assert report.threshold == 0.01
    assert report.total_gains == pytest.approx(
        0.03,
        abs=1e-6,
    )
    assert report.total_losses == pytest.approx(
        0.03,
        abs=1e-6,
    )
    assert report.omega_ratio == pytest.approx(
        1.0,
        abs=1e-6,
    )


def test_omega_report_handles_zero_losses():
    report = PortfolioOmegaRatioReport.from_returns(
        returns=[
            0.01,
            0.02,
            0.03,
        ],
        threshold=0.0,
    )

    assert report.total_losses == 0.0
    assert report.omega_ratio == 0.0


def test_omega_report_preserves_sample_size():
    report = PortfolioOmegaRatioReport.from_returns(
        returns=[
            0.01,
            -0.01,
            0.02,
        ],
    )

    assert report.sample_size == 3


def test_omega_report_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioOmegaRatioReport.from_returns(
            returns=[],
        )


def test_omega_report_is_immutable():
    report = PortfolioOmegaRatioReport.from_returns(
        returns=[
            0.01,
            -0.01,
        ],
    )

    with pytest.raises(
        AttributeError,
    ):
        report.omega_ratio = 0.0
