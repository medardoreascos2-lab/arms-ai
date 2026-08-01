import pytest

from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
    MonteCarloSimulatorV2,
)


def build_trade_pnls():

    return [
        100.0,
        -50.0,
        80.0,
        -30.0,
        120.0,
        -70.0,
    ]


def test_runs_requested_number_of_simulations():

    simulator = MonteCarloSimulatorV2(
        simulations=100,
        random_seed=42,
    )

    result = simulator.simulate(
        trade_pnls=build_trade_pnls(),
        starting_balance=10000.0,
    )

    assert isinstance(
        result,
        MonteCarloSimulationResultV2,
    )

    assert result.total_simulations == 100

    assert len(
        result.final_equities
    ) == 100

    assert len(
        result.maximum_drawdowns
    ) == 100


def test_preserves_final_equity_when_only_order_changes():

    simulator = MonteCarloSimulatorV2(
        simulations=25,
        random_seed=42,
    )

    result = simulator.simulate(
        trade_pnls=build_trade_pnls(),
        starting_balance=10000.0,
    )

    expected_final_equity = (
        10000.0
        + sum(
            build_trade_pnls()
        )
    )

    assert all(
        equity
        == pytest.approx(
            expected_final_equity
        )
        for equity in result.final_equities
    )


def test_calculates_non_negative_drawdowns():

    result = MonteCarloSimulatorV2(
        simulations=50,
        random_seed=7,
    ).simulate(
        trade_pnls=build_trade_pnls(),
        starting_balance=10000.0,
    )

    assert all(
        drawdown >= 0.0
        for drawdown in result.maximum_drawdowns
    )


def test_is_reproducible_with_same_seed():

    first = MonteCarloSimulatorV2(
        simulations=50,
        random_seed=123,
    ).simulate(
        trade_pnls=build_trade_pnls(),
        starting_balance=10000.0,
    )

    second = MonteCarloSimulatorV2(
        simulations=50,
        random_seed=123,
    ).simulate(
        trade_pnls=build_trade_pnls(),
        starting_balance=10000.0,
    )

    assert (
        first.maximum_drawdowns
        == second.maximum_drawdowns
    )

    assert (
        first.equity_curves
        == second.equity_curves
    )


def test_summary_contains_core_metrics():

    result = MonteCarloSimulatorV2(
        simulations=20,
        random_seed=42,
    ).simulate(
        trade_pnls=build_trade_pnls(),
        starting_balance=10000.0,
    )

    summary = result.summary()

    assert summary[
        "total_simulations"
    ] == 20

    assert summary[
        "starting_balance"
    ] == 10000.0

    assert summary[
        "average_final_equity"
    ] == pytest.approx(
        10150.0
    )

    assert summary[
        "worst_maximum_drawdown"
    ] >= 0.0

    assert summary[
        "average_maximum_drawdown"
    ] >= 0.0


def test_to_dict_returns_safe_copy():

    result = MonteCarloSimulatorV2(
        simulations=10,
        random_seed=42,
    ).simulate(
        trade_pnls=build_trade_pnls(),
        starting_balance=10000.0,
    )

    payload = result.to_dict()

    payload["equity_curves"][0][0] = 0.0

    assert (
        result.equity_curves[0][0]
        == 10000.0
    )


@pytest.mark.parametrize(
    "simulations",
    [
        0,
        -1,
    ],
)
def test_rejects_non_positive_simulations(
    simulations,
):

    with pytest.raises(
        ValueError,
        match="simulations",
    ):
        MonteCarloSimulatorV2(
            simulations=simulations,
        )


def test_rejects_non_integer_simulations():

    with pytest.raises(
        TypeError,
        match="simulations",
    ):
        MonteCarloSimulatorV2(
            simulations="100",
        )


@pytest.mark.parametrize(
    "trade_pnls",
    [
        None,
        10,
        "trades",
        {},
    ],
)
def test_rejects_invalid_trade_pnls(
    trade_pnls,
):

    simulator = MonteCarloSimulatorV2(
        simulations=10,
    )

    with pytest.raises(
        TypeError,
        match="trade_pnls",
    ):
        simulator.simulate(
            trade_pnls=trade_pnls,
            starting_balance=10000.0,
        )


def test_rejects_empty_trade_pnls():

    simulator = MonteCarloSimulatorV2(
        simulations=10,
    )

    with pytest.raises(
        ValueError,
        match="trade_pnls",
    ):
        simulator.simulate(
            trade_pnls=[],
            starting_balance=10000.0,
        )


def test_rejects_invalid_starting_balance():

    simulator = MonteCarloSimulatorV2(
        simulations=10,
    )

    with pytest.raises(
        ValueError,
        match="starting_balance",
    ):
        simulator.simulate(
            trade_pnls=build_trade_pnls(),
            starting_balance=0.0,
        )
