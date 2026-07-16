import pytest

from backend.backtesting.monte_carlo_engine import (
    MonteCarloEngine,
    MonteCarloSimulation,
)


def test_monte_carlo_engine_runs_expected_number_of_simulations():
    engine = MonteCarloEngine(
        simulations=100,
        seed=42,
    )

    result = engine.run(
        pnls=[
            10.0,
            -5.0,
            20.0,
        ],
        initial_balance=1000.0,
    )

    assert len(result.simulations) == 100
    assert result.total_simulations == 100

    assert all(
        isinstance(
            simulation,
            MonteCarloSimulation,
        )
        for simulation in result.simulations
    )


def test_monte_carlo_engine_preserves_total_profit():
    engine = MonteCarloEngine(
        simulations=25,
        seed=42,
    )

    result = engine.run(
        pnls=[
            10.0,
            -5.0,
            20.0,
        ],
        initial_balance=1000.0,
    )

    assert all(
        simulation.final_balance == 1025.0
        for simulation in result.simulations
    )

    assert all(
        simulation.net_profit == 25.0
        for simulation in result.simulations
    )


def test_monte_carlo_engine_calculates_drawdown():
    engine = MonteCarloEngine(
        simulations=1,
        seed=1,
    )

    result = engine.run(
        pnls=[
            100.0,
            -150.0,
            200.0,
        ],
        initial_balance=1000.0,
    )

    simulation = result.simulations[0]

    assert simulation.max_drawdown >= 0.0
    assert simulation.peak_balance >= 1000.0
    assert simulation.final_balance == 1150.0


def test_monte_carlo_engine_is_reproducible_with_seed():
    first = MonteCarloEngine(
        simulations=20,
        seed=123,
    ).run(
        pnls=[
            10.0,
            -5.0,
            20.0,
            -2.0,
        ],
        initial_balance=1000.0,
    )

    second = MonteCarloEngine(
        simulations=20,
        seed=123,
    ).run(
        pnls=[
            10.0,
            -5.0,
            20.0,
            -2.0,
        ],
        initial_balance=1000.0,
    )

    assert first.simulations == second.simulations


def test_monte_carlo_engine_rejects_empty_pnls():
    engine = MonteCarloEngine(
        simulations=10,
    )

    with pytest.raises(
        ValueError,
        match="pnls",
    ):
        engine.run(
            pnls=[],
            initial_balance=1000.0,
        )


@pytest.mark.parametrize(
    "simulations",
    [
        0,
        -1,
    ],
)
def test_monte_carlo_engine_rejects_invalid_simulations(
    simulations,
):
    with pytest.raises(
        ValueError,
        match="simulations",
    ):
        MonteCarloEngine(
            simulations=simulations,
        )


@pytest.mark.parametrize(
    "initial_balance",
    [
        0,
        -100.0,
    ],
)
def test_monte_carlo_engine_rejects_invalid_initial_balance(
    initial_balance,
):
    engine = MonteCarloEngine(
        simulations=10,
    )

    with pytest.raises(
        ValueError,
        match="initial_balance",
    ):
        engine.run(
            pnls=[10.0],
            initial_balance=initial_balance,
        )
