import pytest

from backend.backtesting.parameter_evaluator import (
    ParameterEvaluation,
)
from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
)
from backend.backtesting.walk_forward_optimizer import (
    WalkForwardOptimizationResult,
)


def build_evaluation(
    *,
    parameters,
    net_profit,
    profit_factor=1.5,
    max_drawdown=5.0,
    win_rate=60.0,
):
    return ParameterEvaluation(
        parameters=dict(parameters),
        net_profit=net_profit,
        profit_factor=profit_factor,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        result=object(),
    )


def build_result(
    *,
    parameters,
    training_profit,
    testing_profit,
):
    training = build_evaluation(
        parameters=parameters,
        net_profit=training_profit,
    )

    testing = build_evaluation(
        parameters=parameters,
        net_profit=testing_profit,
    )

    return WalkForwardOptimizationResult(
        selected_parameters=dict(parameters),
        training_evaluation=training,
        testing_evaluation=testing,
        training_evaluations=[training],
    )


def test_optimization_report_builds_window_details():
    report = WalkForwardOptimizationReport.from_results(
        [
            build_result(
                parameters={
                    "ema_period": 20,
                    "rsi_period": 14,
                },
                training_profit=100.0,
                testing_profit=40.0,
            ),
            build_result(
                parameters={
                    "ema_period": 50,
                    "rsi_period": 21,
                },
                training_profit=80.0,
                testing_profit=-10.0,
            ),
        ]
    )

    assert report.total_windows == 2
    assert len(report.windows) == 2

    first = report.windows[0]

    assert first.window_number == 1
    assert first.selected_parameters == {
        "ema_period": 20,
        "rsi_period": 14,
    }
    assert first.training_net_profit == 100.0
    assert first.testing_net_profit == 40.0
    assert first.performance_degradation == 60.0
    assert first.degradation_rate == 60.0

    second = report.windows[1]

    assert second.window_number == 2
    assert second.testing_net_profit == -10.0
    assert second.overfit_suspected is True


def test_optimization_report_calculates_summary():
    report = WalkForwardOptimizationReport.from_results(
        [
            build_result(
                parameters={"name": "A"},
                training_profit=100.0,
                testing_profit=40.0,
            ),
            build_result(
                parameters={"name": "B"},
                training_profit=80.0,
                testing_profit=-10.0,
            ),
            build_result(
                parameters={"name": "C"},
                training_profit=60.0,
                testing_profit=20.0,
            ),
        ]
    )

    assert report.total_windows == 3
    assert report.profitable_testing_windows == 2
    assert report.losing_testing_windows == 1

    assert report.total_training_net_profit == 240.0
    assert report.total_testing_net_profit == 50.0

    assert report.average_training_net_profit == 80.0
    assert report.average_testing_net_profit == pytest.approx(
        16.67,
        abs=0.01,
    )

    assert report.average_performance_degradation == pytest.approx(
        63.33,
        abs=0.01,
    )

    assert report.testing_profitable_rate == pytest.approx(
        66.67,
        abs=0.01,
    )


def test_optimization_report_detects_overfitting():
    report = WalkForwardOptimizationReport.from_results(
        [
            build_result(
                parameters={"name": "A"},
                training_profit=100.0,
                testing_profit=80.0,
            ),
            build_result(
                parameters={"name": "B"},
                training_profit=100.0,
                testing_profit=20.0,
            ),
            build_result(
                parameters={"name": "C"},
                training_profit=50.0,
                testing_profit=-5.0,
            ),
        ]
    )

    assert report.overfit_windows == 2
    assert report.overfit_rate == pytest.approx(
        66.67,
        abs=0.01,
    )

    assert report.windows[0].overfit_suspected is False
    assert report.windows[1].overfit_suspected is True
    assert report.windows[2].overfit_suspected is True


def test_optimization_report_handles_zero_training_profit():
    report = WalkForwardOptimizationReport.from_results(
        [
            build_result(
                parameters={"name": "A"},
                training_profit=0.0,
                testing_profit=10.0,
            )
        ]
    )

    window = report.windows[0]

    assert window.performance_degradation == -10.0
    assert window.degradation_rate == 0.0
    assert window.overfit_suspected is False


def test_optimization_report_handles_empty_results():
    report = WalkForwardOptimizationReport.from_results([])

    assert report.total_windows == 0
    assert report.profitable_testing_windows == 0
    assert report.losing_testing_windows == 0
    assert report.breakeven_testing_windows == 0

    assert report.total_training_net_profit == 0.0
    assert report.total_testing_net_profit == 0.0
    assert report.average_training_net_profit == 0.0
    assert report.average_testing_net_profit == 0.0
    assert report.average_performance_degradation == 0.0

    assert report.testing_profitable_rate == 0.0
    assert report.overfit_windows == 0
    assert report.overfit_rate == 0.0
    assert report.windows == []


def test_optimization_report_preserves_parameter_copy():
    parameters = {
        "ema_period": 20,
    }

    result = build_result(
        parameters=parameters,
        training_profit=10.0,
        testing_profit=5.0,
    )

    report = WalkForwardOptimizationReport.from_results(
        [result]
    )

    result.selected_parameters["ema_period"] = 200

    assert report.windows[0].selected_parameters == {
        "ema_period": 20,
    }
