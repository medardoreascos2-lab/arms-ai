import pytest

from backend.portfolio.portfolio_monte_carlo_engine import (
    PortfolioMonteCarloEngine,
)


def test_monte_carlo_runs_requested_simulations():
    result = PortfolioMonteCarloEngine.run(
        initial_value=1000.0,
        mean_return=0.001,
        volatility=0.01,
        periods=10,
        simulations=100,
        seed=42,
    )

    assert result.simulations == 100
    assert result.periods == 10
    assert len(result.final_values) == 100


def test_monte_carlo_is_reproducible_with_seed():
    first = PortfolioMonteCarloEngine.run(
        initial_value=1000.0,
        mean_return=0.001,
        volatility=0.01,
        periods=10,
        simulations=50,
        seed=42,
    )

    second = PortfolioMonteCarloEngine.run(
        initial_value=1000.0,
        mean_return=0.001,
        volatility=0.01,
        periods=10,
        simulations=50,
        seed=42,
    )

    assert first.final_values == second.final_values
    assert first.mean_final_value == second.mean_final_value


def test_monte_carlo_calculates_summary_metrics():
    result = PortfolioMonteCarloEngine.run(
        initial_value=1000.0,
        mean_return=0.001,
        volatility=0.01,
        periods=20,
        simulations=200,
        seed=7,
    )

    assert result.minimum_final_value <= result.mean_final_value
    assert result.mean_final_value <= result.maximum_final_value

    assert result.percentile_5 <= result.median_final_value
    assert result.median_final_value <= result.percentile_95


def test_monte_carlo_calculates_probability_of_loss():
    result = PortfolioMonteCarloEngine.run(
        initial_value=1000.0,
        mean_return=-0.01,
        volatility=0.0,
        periods=2,
        simulations=10,
        seed=1,
    )

    assert result.probability_of_loss == 100.0


def test_monte_carlo_handles_zero_volatility():
    result = PortfolioMonteCarloEngine.run(
        initial_value=1000.0,
        mean_return=0.01,
        volatility=0.0,
        periods=2,
        simulations=5,
        seed=1,
    )

    expected = 1000.0 * 1.01 * 1.01

    assert result.minimum_final_value == pytest.approx(
        expected,
        abs=1e-6,
    )
    assert result.maximum_final_value == pytest.approx(
        expected,
        abs=1e-6,
    )


def test_monte_carlo_rejects_invalid_initial_value():
    with pytest.raises(
        ValueError,
        match="initial_value",
    ):
        PortfolioMonteCarloEngine.run(
            initial_value=0.0,
            mean_return=0.01,
            volatility=0.10,
            periods=10,
            simulations=100,
        )


@pytest.mark.parametrize(
    "periods",
    [
        0,
        -1,
    ],
)
def test_monte_carlo_rejects_invalid_periods(
    periods,
):
    with pytest.raises(
        ValueError,
        match="periods",
    ):
        PortfolioMonteCarloEngine.run(
            initial_value=1000.0,
            mean_return=0.01,
            volatility=0.10,
            periods=periods,
            simulations=100,
        )


@pytest.mark.parametrize(
    "simulations",
    [
        0,
        -1,
    ],
)
def test_monte_carlo_rejects_invalid_simulations(
    simulations,
):
    with pytest.raises(
        ValueError,
        match="simulations",
    ):
        PortfolioMonteCarloEngine.run(
            initial_value=1000.0,
            mean_return=0.01,
            volatility=0.10,
            periods=10,
            simulations=simulations,
        )


def test_monte_carlo_rejects_negative_volatility():
    with pytest.raises(
        ValueError,
        match="volatility",
    ):
        PortfolioMonteCarloEngine.run(
            initial_value=1000.0,
            mean_return=0.01,
            volatility=-0.10,
            periods=10,
            simulations=100,
        )


def test_monte_carlo_result_is_immutable():
    result = PortfolioMonteCarloEngine.run(
        initial_value=1000.0,
        mean_return=0.01,
        volatility=0.10,
        periods=2,
        simulations=5,
        seed=1,
    )

    with pytest.raises(
        AttributeError,
    ):
        result.mean_final_value = 0.0
