import pytest

from backend.portfolio.portfolio_statistics import (
    PortfolioStatistics,
)


def test_statistics_calculates_mean_return():
    statistics = PortfolioStatistics.from_returns(
        returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
        ],
    )

    assert statistics.mean_return == pytest.approx(
        0.0125,
        abs=1e-6,
    )


def test_statistics_calculates_sample_volatility():
    statistics = PortfolioStatistics.from_returns(
        returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
        ],
    )

    assert statistics.volatility == pytest.approx(
        0.017078,
        abs=1e-6,
    )


def test_statistics_calculates_annualized_metrics():
    statistics = PortfolioStatistics.from_returns(
        returns=[
            0.01,
            0.02,
            -0.01,
            0.03,
        ],
        periods_per_year=252,
    )

    assert statistics.annualized_return == pytest.approx(
        statistics.mean_return * 252,
        abs=1e-6,
    )

    assert statistics.annualized_volatility == pytest.approx(
        statistics.volatility
        * 252 ** 0.5,
        abs=1e-6,
    )


def test_statistics_calculates_downside_deviation():
    statistics = PortfolioStatistics.from_returns(
        returns=[
            0.02,
            -0.01,
            -0.03,
            0.01,
        ],
        minimum_acceptable_return=0.0,
    )

    assert statistics.downside_deviation == pytest.approx(
        0.015811,
        abs=1e-6,
    )


def test_statistics_calculates_cumulative_return():
    statistics = PortfolioStatistics.from_returns(
        returns=[
            0.10,
            -0.05,
        ],
    )

    assert statistics.cumulative_return == pytest.approx(
        0.045,
        abs=1e-6,
    )


def test_statistics_preserves_sample_size():
    statistics = PortfolioStatistics.from_returns(
        returns=[
            0.01,
            0.02,
            0.03,
        ],
    )

    assert statistics.sample_size == 3


def test_statistics_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        PortfolioStatistics.from_returns(
            returns=[],
        )


def test_statistics_rejects_single_return():
    with pytest.raises(
        ValueError,
        match="al menos 2",
    ):
        PortfolioStatistics.from_returns(
            returns=[
                0.01,
            ],
        )


def test_statistics_rejects_invalid_periods():
    with pytest.raises(
        ValueError,
        match="periods_per_year",
    ):
        PortfolioStatistics.from_returns(
            returns=[
                0.01,
                0.02,
            ],
            periods_per_year=0,
        )


def test_statistics_is_immutable():
    statistics = PortfolioStatistics.from_returns(
        returns=[
            0.01,
            0.02,
        ],
    )

    with pytest.raises(
        AttributeError,
    ):
        statistics.mean_return = 0.0
