import pytest

from backend.portfolio.portfolio_beta_report import (
    PortfolioBetaReport,
)


def test_beta_report_calculates_beta():
    report = PortfolioBetaReport.from_returns(
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
    )

    assert report.beta > 0.0


def test_beta_report_calculates_covariance():
    report = PortfolioBetaReport.from_returns(
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
    )

    assert report.covariance != 0.0
    assert report.benchmark_variance > 0.0


def test_beta_report_classifies_portfolio():
    report = PortfolioBetaReport.from_returns(
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
    )

    assert report.classification in {
        "Defensive",
        "Neutral",
        "Aggressive",
    }


def test_beta_report_preserves_sample_size():
    report = PortfolioBetaReport.from_returns(
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


def test_beta_report_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioBetaReport.from_returns(
            portfolio_returns=[],
            benchmark_returns=[],
        )


def test_beta_report_rejects_different_lengths():
    with pytest.raises(
        ValueError,
        match="length",
    ):
        PortfolioBetaReport.from_returns(
            portfolio_returns=[
                0.01,
            ],
            benchmark_returns=[
                0.01,
                0.02,
            ],
        )


def test_beta_report_rejects_single_observation():
    with pytest.raises(
        ValueError,
        match="al menos 2",
    ):
        PortfolioBetaReport.from_returns(
            portfolio_returns=[
                0.01,
            ],
            benchmark_returns=[
                0.00,
            ],
        )


def test_beta_report_is_immutable():
    report = PortfolioBetaReport.from_returns(
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
        report.beta = 0.0
