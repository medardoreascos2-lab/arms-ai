import pytest

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)
from backend.backtesting.strategy_validation_result_v2 import (
    StrategyValidationResultV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


def build_walk_forward_result():

    return WalkForwardOptimizationResultV2(
        window_results=[
            {
                "window_index": 0,
                "success": True,
                "training_score": 90.0,
                "testing_score": 82.0,
                "testing_net_pnl": 300.0,
                "testing_win_rate": 0.60,
                "testing_maximum_drawdown": 120.0,
                "best_parameters": {
                    "ema": 50,
                },
            },
        ],
    )


def build_monte_carlo_report():

    simulation = MonteCarloSimulationResultV2(
        starting_balance=10000.0,
        final_equities=[
            10150.0,
            10050.0,
        ],
        maximum_drawdowns=[
            60.0,
            120.0,
        ],
        equity_curves=[
            [
                10000.0,
                10100.0,
                10150.0,
            ],
            [
                10000.0,
                10020.0,
                10050.0,
            ],
        ],
    )

    return MonteCarloReportV2(
        simulation_result=simulation,
    )


def test_builds_strategy_validation_result():

    result = StrategyValidationResultV2(
        backtest_score=87.5,
        walk_forward_result=build_walk_forward_result(),
        monte_carlo_report=build_monte_carlo_report(),
    )

    assert result.backtest_score == 87.5
    assert result.walk_forward_result.total_windows == 1
    assert (
        result.monte_carlo_report.summary()[
            "total_simulations"
        ]
        == 2
    )


def test_validation_score_is_average():

    result = StrategyValidationResultV2(
        backtest_score=90.0,
        walk_forward_result=build_walk_forward_result(),
        monte_carlo_report=build_monte_carlo_report(),
    )

    assert result.validation_score == pytest.approx(
        (
            90.0
            + 82.0
            + 10100.0 / 100
        )
        / 3
    )


def test_to_dict_returns_safe_copy():

    result = StrategyValidationResultV2(
        backtest_score=90.0,
        walk_forward_result=build_walk_forward_result(),
        monte_carlo_report=build_monte_carlo_report(),
    )

    payload = result.to_dict()

    payload["walk_forward"][
        "window_results"
    ][0]["testing_score"] = 0.0

    assert (
        result.walk_forward_result
        .window_results[0]["testing_score"]
        == 82.0
    )


def test_rejects_invalid_backtest_score():

    with pytest.raises(TypeError):

        StrategyValidationResultV2(
            backtest_score="90",
            walk_forward_result=build_walk_forward_result(),
            monte_carlo_report=build_monte_carlo_report(),
        )


def test_rejects_invalid_walk_forward_result():

    with pytest.raises(TypeError):

        StrategyValidationResultV2(
            backtest_score=90.0,
            walk_forward_result={},
            monte_carlo_report=build_monte_carlo_report(),
        )


def test_rejects_invalid_monte_carlo_report():

    with pytest.raises(TypeError):

        StrategyValidationResultV2(
            backtest_score=90.0,
            walk_forward_result=build_walk_forward_result(),
            monte_carlo_report={},
        )
