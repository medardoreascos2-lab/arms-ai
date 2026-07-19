import pytest

from backend.portfolio.portfolio_rebalancing_engine import (
    PortfolioRebalancingEngine,
)


def test_rebalancing_calculates_trades():
    report = PortfolioRebalancingEngine.rebalance(
        current_weights={
            "A": 50.0,
            "B": 30.0,
            "C": 20.0,
        },
        target_weights={
            "A": 40.0,
            "B": 40.0,
            "C": 20.0,
        },
    )

    assert report.trades["A"] == -10.0
    assert report.trades["B"] == 10.0
    assert report.trades["C"] == 0.0


def test_rebalancing_calculates_turnover():
    report = PortfolioRebalancingEngine.rebalance(
        current_weights={
            "A": 60.0,
            "B": 40.0,
        },
        target_weights={
            "A": 50.0,
            "B": 50.0,
        },
    )

    assert report.turnover == pytest.approx(
        10.0,
        abs=1e-6,
    )


def test_rebalancing_respects_tolerance():
    report = PortfolioRebalancingEngine.rebalance(
        current_weights={
            "A": 50.1,
            "B": 49.9,
        },
        target_weights={
            "A": 50.0,
            "B": 50.0,
        },
        tolerance=0.5,
    )

    assert report.turnover == 0.0

    assert all(
        trade == 0.0
        for trade in report.trades.values()
    )


def test_rebalancing_identifies_overweight_assets():
    report = PortfolioRebalancingEngine.rebalance(
        current_weights={
            "A": 70.0,
            "B": 30.0,
        },
        target_weights={
            "A": 50.0,
            "B": 50.0,
        },
    )

    assert report.overweight_assets == (
        "A",
    )

    assert report.underweight_assets == (
        "B",
    )


def test_rebalancing_preserves_assets():
    report = PortfolioRebalancingEngine.rebalance(
        current_weights={
            "A": 50.0,
            "B": 50.0,
        },
        target_weights={
            "A": 50.0,
            "B": 50.0,
        },
    )

    assert report.assets == (
        "A",
        "B",
    )


def test_rebalancing_rejects_missing_assets():
    with pytest.raises(
        ValueError,
        match="assets",
    ):
        PortfolioRebalancingEngine.rebalance(
            current_weights={
                "A": 100.0,
            },
            target_weights={
                "B": 100.0,
            },
        )


def test_rebalancing_rejects_invalid_tolerance():
    with pytest.raises(
        ValueError,
        match="tolerance",
    ):
        PortfolioRebalancingEngine.rebalance(
            current_weights={
                "A": 100.0,
            },
            target_weights={
                "A": 100.0,
            },
            tolerance=-1.0,
        )


def test_rebalancing_is_immutable():
    report = PortfolioRebalancingEngine.rebalance(
        current_weights={
            "A": 100.0,
        },
        target_weights={
            "A": 100.0,
        },
    )

    with pytest.raises(
        AttributeError,
    ):
        report.turnover = 0.0
