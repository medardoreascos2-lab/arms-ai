import pytest

from backend.application.simulate_portfolio import (
    SimulatePortfolio,
)
from backend.portfolio.portfolio_monte_carlo_engine import (
    PortfolioMonteCarloEngine,
)


def test_use_case_returns_simulation():
    use_case = SimulatePortfolio()

    result = use_case.execute(
        initial_value=1000.0,
        mean_return=0.01,
        volatility=0.10,
        periods=12,
        simulations=100,
        seed=42,
    )

    assert isinstance(
        result,
        PortfolioMonteCarloEngine,
    )


def test_use_case_preserves_simulation_size():
    use_case = SimulatePortfolio()

    result = use_case.execute(
        initial_value=1000.0,
        mean_return=0.01,
        volatility=0.10,
        periods=12,
        simulations=250,
        seed=42,
    )

    assert result.simulations == 250
    assert len(result.final_values) == 250


def test_use_case_accepts_injected_engine():
    class FakeEngine:
        @staticmethod
        def run(**kwargs):
            return PortfolioMonteCarloEngine.run(
                **kwargs
            )

    use_case = SimulatePortfolio(
        engine=FakeEngine,
    )

    result = use_case.execute(
        initial_value=1000.0,
        mean_return=0.01,
        volatility=0.10,
        periods=12,
        simulations=10,
    )

    assert isinstance(
        result,
        PortfolioMonteCarloEngine,
    )


def test_use_case_rejects_invalid_engine():
    with pytest.raises(
        TypeError,
        match="engine",
    ):
        SimulatePortfolio(
            engine=object(),
        )


def test_use_case_rejects_invalid_initial_value():
    use_case = SimulatePortfolio()

    with pytest.raises(
        ValueError,
        match="initial_value",
    ):
        use_case.execute(
            initial_value=0.0,
            mean_return=0.01,
            volatility=0.10,
            periods=12,
            simulations=100,
        )


def test_use_case_is_deterministic():
    use_case = SimulatePortfolio()

    first = use_case.execute(
        initial_value=1000.0,
        mean_return=0.01,
        volatility=0.10,
        periods=12,
        simulations=50,
        seed=123,
    )

    second = use_case.execute(
        initial_value=1000.0,
        mean_return=0.01,
        volatility=0.10,
        periods=12,
        simulations=50,
        seed=123,
    )

    assert first.final_values == second.final_values
