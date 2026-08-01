import pytest

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)
from backend.backtesting.strategy_validation_report_v2 import (
    StrategyValidationReportV2,
)
from backend.backtesting.strategy_validation_result_v2 import (
    StrategyValidationResultV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


def build_validation_result():

    walk_forward = WalkForwardOptimizationResultV2(
        window_results=[
            {
                "window_index": 0,
                "success": True,
                "training_score": 91.0,
                "testing_score": 83.0,
                "testing_net_pnl": 420.0,
                "testing_win_rate": 0.65,
                "testing_maximum_drawdown": 110.0,
                "best_parameters": {
                    "ema": 50,
                },
            },
        ],
    )

    monte_carlo = MonteCarloReportV2(
        simulation_result=MonteCarloSimulationResultV2(
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
    )

    return StrategyValidationResultV2(
        backtest_score=90.0,
        walk_forward_result=walk_forward,
        monte_carlo_report=monte_carlo,
    )


def test_builds_report():

    report = StrategyValidationReportV2(
        validation_result=build_validation_result(),
    )

    assert report.summary()["backtest_score"] == 90.0

    assert report.summary()["walk_forward_score"] == 83.0

    assert report.summary()["total_simulations"] == 2


def test_summary_contains_validation_score():

    report = StrategyValidationReportV2(
        validation_result=build_validation_result(),
    )

    assert report.summary()["validation_score"] == pytest.approx(
        report.validation_result.validation_score
    )


def test_to_dict_returns_complete_report():

    report = StrategyValidationReportV2(
        validation_result=build_validation_result(),
    )

    payload = report.to_dict()

    assert "summary" in payload
    assert "walk_forward" in payload
    assert "monte_carlo" in payload


def test_to_dict_returns_safe_copy():

    report = StrategyValidationReportV2(
        validation_result=build_validation_result(),
    )

    payload = report.to_dict()

    payload["walk_forward"][
        "window_results"
    ][0]["testing_score"] = 0.0

    assert (
        report.to_dict()["walk_forward"][
            "window_results"
        ][0]["testing_score"]
        == 83.0
    )


def test_rejects_invalid_validation_result():

    with pytest.raises(
        TypeError,
        match="StrategyValidationResultV2",
    ):
        StrategyValidationReportV2(
            validation_result={},
        )
