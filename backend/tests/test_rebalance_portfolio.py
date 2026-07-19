import pytest

from backend.application.rebalance_portfolio import (
    RebalancePortfolio,
)
from backend.portfolio.portfolio_rebalancing_engine import (
    PortfolioRebalancingEngine,
)


def build_current_weights():
    return {
        "A": 50.0,
        "B": 30.0,
        "C": 20.0,
    }


def build_target_weights():
    return {
        "A": 40.0,
        "B": 40.0,
        "C": 20.0,
    }


def test_use_case_returns_rebalancing_report():
    use_case = RebalancePortfolio()

    report = use_case.execute(
        current_weights=build_current_weights(),
        target_weights=build_target_weights(),
    )

    assert isinstance(
        report,
        PortfolioRebalancingEngine,
    )


def test_use_case_calculates_trades():
    use_case = RebalancePortfolio()

    report = use_case.execute(
        current_weights=build_current_weights(),
        target_weights=build_target_weights(),
    )

    assert report.trades["A"] == -10.0
    assert report.trades["B"] == 10.0


def test_use_case_accepts_injected_engine():
    class FakeEngine:
        @staticmethod
        def rebalance(
            *,
            current_weights,
            target_weights,
            tolerance=0.0,
        ):
            return PortfolioRebalancingEngine.rebalance(
                current_weights=current_weights,
                target_weights=target_weights,
                tolerance=tolerance,
            )

    use_case = RebalancePortfolio(
        engine=FakeEngine,
    )

    report = use_case.execute(
        current_weights=build_current_weights(),
        target_weights=build_target_weights(),
    )

    assert isinstance(
        report,
        PortfolioRebalancingEngine,
    )


def test_use_case_rejects_invalid_engine():
    with pytest.raises(
        TypeError,
        match="engine",
    ):
        RebalancePortfolio(
            engine=object(),
        )


def test_use_case_rejects_invalid_assets():
    use_case = RebalancePortfolio()

    with pytest.raises(
        ValueError,
        match="assets",
    ):
        use_case.execute(
            current_weights={"A": 100.0},
            target_weights={"B": 100.0},
        )


def test_use_case_supports_tolerance():
    use_case = RebalancePortfolio()

    report = use_case.execute(
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
