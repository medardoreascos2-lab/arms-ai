import pytest

from backend.portfolio.benchmark_analytics import (
    BenchmarkAnalytics,
)


def build_portfolio_returns() -> list[float]:
    return [
        0.012,
        -0.008,
        0.015,
        0.004,
        -0.010,
        0.018,
        0.006,
        -0.003,
    ]


def build_benchmark_returns() -> list[float]:
    return [
        0.010,
        -0.006,
        0.011,
        0.003,
        -0.008,
        0.013,
        0.004,
        -0.002,
    ]


def test_returns_benchmark_metrics():
    result = BenchmarkAnalytics().calculate(
        portfolio_returns=build_portfolio_returns(),
        benchmark_returns=build_benchmark_returns(),
        risk_free_rate=0.02,
    )

    assert "beta" in result
    assert "alpha" in result
    assert "tracking_error" in result
    assert "information_ratio" in result
    assert "portfolio_curve" in result
    assert "benchmark_curve" in result


def test_curves_have_same_length_as_returns_plus_one():
    result = BenchmarkAnalytics().calculate(
        portfolio_returns=build_portfolio_returns(),
        benchmark_returns=build_benchmark_returns(),
    )

    assert len(result["portfolio_curve"]) == 9
    assert len(result["benchmark_curve"]) == 9


def test_beta_is_finite():
    result = BenchmarkAnalytics().calculate(
        portfolio_returns=build_portfolio_returns(),
        benchmark_returns=build_benchmark_returns(),
    )

    assert result["beta"] == pytest.approx(
        float(result["beta"])
    )


def test_rejects_different_series_lengths():
    with pytest.raises(
        ValueError,
        match="misma longitud",
    ):
        BenchmarkAnalytics().calculate(
            portfolio_returns=[0.01, 0.02],
            benchmark_returns=[0.01],
        )


def test_rejects_empty_returns():
    with pytest.raises(
        ValueError,
        match="returns",
    ):
        BenchmarkAnalytics().calculate(
            portfolio_returns=[],
            benchmark_returns=[],
        )
