import pytest

from backend.portfolio.performance_attribution import (
    PerformanceAttribution,
)


def portfolio_weights():
    return {
        "AAPL": 0.40,
        "MSFT": 0.35,
        "NVDA": 0.25,
    }


def benchmark_weights():
    return {
        "AAPL": 0.30,
        "MSFT": 0.40,
        "NVDA": 0.30,
    }


def portfolio_returns():
    return {
        "AAPL": 0.18,
        "MSFT": 0.12,
        "NVDA": 0.30,
    }


def benchmark_returns():
    return {
        "AAPL": 0.15,
        "MSFT": 0.11,
        "NVDA": 0.22,
    }


def test_returns_brinson_metrics():
    result = PerformanceAttribution().calculate(
        portfolio_weights=portfolio_weights(),
        benchmark_weights=benchmark_weights(),
        portfolio_returns=portfolio_returns(),
        benchmark_returns=benchmark_returns(),
    )

    assert "portfolio_return" in result
    assert "benchmark_return" in result
    assert "active_return" in result
    assert "allocation_effect" in result
    assert "selection_effect" in result
    assert "asset_contributions" in result
    assert "best_asset" in result
    assert "worst_asset" in result


def test_active_return_matches_difference():
    result = PerformanceAttribution().calculate(
        portfolio_weights=portfolio_weights(),
        benchmark_weights=benchmark_weights(),
        portfolio_returns=portfolio_returns(),
        benchmark_returns=benchmark_returns(),
    )

    assert result["active_return"] == pytest.approx(
        result["portfolio_return"]
        - result["benchmark_return"]
    )


def test_asset_contributions_sum_to_active_return():
    result = PerformanceAttribution().calculate(
        portfolio_weights=portfolio_weights(),
        benchmark_weights=benchmark_weights(),
        portfolio_returns=portfolio_returns(),
        benchmark_returns=benchmark_returns(),
    )

    assert sum(
        result["asset_contributions"].values()
    ) == pytest.approx(
        result["active_return"]
    )


def test_rejects_weight_sum():
    with pytest.raises(
        ValueError,
        match="weights",
    ):
        PerformanceAttribution().calculate(
            portfolio_weights={
                "AAPL":0.5,
                "MSFT":0.2,
            },
            benchmark_weights={
                "AAPL":0.5,
                "MSFT":0.5,
            },
            portfolio_returns={
                "AAPL":0.1,
                "MSFT":0.2,
            },
            benchmark_returns={
                "AAPL":0.1,
                "MSFT":0.2,
            },
        )


def test_rejects_missing_assets():
    with pytest.raises(
        ValueError,
        match="assets",
    ):
        PerformanceAttribution().calculate(
            portfolio_weights=portfolio_weights(),
            benchmark_weights=benchmark_weights(),
            portfolio_returns={
                "AAPL":0.1,
            },
            benchmark_returns=benchmark_returns(),
        )
