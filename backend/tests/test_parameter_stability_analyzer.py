import pytest

from backend.backtesting.parameter_stability_analyzer import (
    ParameterStabilityAnalyzer,
)
from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
    WalkForwardOptimizationWindowReport,
)


def build_report() -> WalkForwardOptimizationReport:
    return WalkForwardOptimizationReport(
        total_windows=4,
        profitable_testing_windows=3,
        losing_testing_windows=1,
        breakeven_testing_windows=0,
        total_training_net_profit=200.0,
        total_testing_net_profit=120.0,
        average_training_net_profit=50.0,
        average_testing_net_profit=30.0,
        average_performance_degradation=20.0,
        testing_profitable_rate=75.0,
        overfit_windows=1,
        overfit_rate=25.0,
        windows=[
            WalkForwardOptimizationWindowReport(
                window_number=1,
                selected_parameters={
                    "ema_period": 25,
                    "rsi_period": 10,
                    "atr_period": 10,
                    "risk_percent": 0.75,
                },
                training_net_profit=40.0,
                testing_net_profit=20.0,
                performance_degradation=20.0,
                degradation_rate=50.0,
                overfit_suspected=False,
            ),
            WalkForwardOptimizationWindowReport(
                window_number=2,
                selected_parameters={
                    "ema_period": 25,
                    "rsi_period": 14,
                    "atr_period": 10,
                    "risk_percent": 0.75,
                },
                training_net_profit=50.0,
                testing_net_profit=30.0,
                performance_degradation=20.0,
                degradation_rate=40.0,
                overfit_suspected=False,
            ),
            WalkForwardOptimizationWindowReport(
                window_number=3,
                selected_parameters={
                    "ema_period": 25,
                    "rsi_period": 21,
                    "atr_period": 20,
                    "risk_percent": 0.75,
                },
                training_net_profit=60.0,
                testing_net_profit=50.0,
                performance_degradation=10.0,
                degradation_rate=16.67,
                overfit_suspected=False,
            ),
            WalkForwardOptimizationWindowReport(
                window_number=4,
                selected_parameters={
                    "ema_period": 50,
                    "rsi_period": 14,
                    "atr_period": 10,
                    "risk_percent": 0.5,
                },
                training_net_profit=50.0,
                testing_net_profit=20.0,
                performance_degradation=30.0,
                degradation_rate=60.0,
                overfit_suspected=True,
            ),
        ],
    )


def test_analyzer_builds_parameter_summaries():
    analysis = ParameterStabilityAnalyzer().analyze(
        report=build_report(),
    )

    assert analysis.total_windows == 4
    assert set(analysis.parameters) == {
        "ema_period",
        "rsi_period",
        "atr_period",
        "risk_percent",
    }


def test_analyzer_finds_dominant_value():
    analysis = ParameterStabilityAnalyzer().analyze(
        report=build_report(),
    )

    ema = analysis.parameters["ema_period"]

    assert ema.dominant_value == 25
    assert ema.dominant_count == 3
    assert ema.dominant_rate == 75.0

    risk = analysis.parameters["risk_percent"]

    assert risk.dominant_value == 0.75
    assert risk.dominant_count == 3
    assert risk.dominant_rate == 75.0


def test_analyzer_tracks_value_frequencies():
    analysis = ParameterStabilityAnalyzer().analyze(
        report=build_report(),
    )

    rsi = analysis.parameters["rsi_period"]

    assert rsi.frequencies == {
        10: 1,
        14: 2,
        21: 1,
    }

    atr = analysis.parameters["atr_period"]

    assert atr.frequencies == {
        10: 3,
        20: 1,
    }


def test_analyzer_calculates_stability_score():
    analysis = ParameterStabilityAnalyzer().analyze(
        report=build_report(),
    )

    ema = analysis.parameters["ema_period"]
    rsi = analysis.parameters["rsi_period"]

    assert ema.stability_score == 75.0
    assert rsi.stability_score == 50.0
    assert ema.stability_score > rsi.stability_score


def test_analyzer_calculates_overall_stability():
    analysis = ParameterStabilityAnalyzer().analyze(
        report=build_report(),
    )

    expected = (
        75.0
        + 50.0
        + 75.0
        + 75.0
    ) / 4

    assert analysis.overall_stability_score == pytest.approx(
        expected
    )


def test_analyzer_handles_empty_report():
    report = WalkForwardOptimizationReport(
        total_windows=0,
        profitable_testing_windows=0,
        losing_testing_windows=0,
        breakeven_testing_windows=0,
        total_training_net_profit=0.0,
        total_testing_net_profit=0.0,
        average_training_net_profit=0.0,
        average_testing_net_profit=0.0,
        average_performance_degradation=0.0,
        testing_profitable_rate=0.0,
        overfit_windows=0,
        overfit_rate=0.0,
        windows=[],
    )

    analysis = ParameterStabilityAnalyzer().analyze(
        report=report,
    )

    assert analysis.total_windows == 0
    assert analysis.parameters == {}
    assert analysis.overall_stability_score == 0.0


def test_analyzer_handles_missing_parameter_in_some_windows():
    report = build_report()

    report.windows[3].selected_parameters.pop(
        "risk_percent"
    )

    analysis = ParameterStabilityAnalyzer().analyze(
        report=report,
    )

    risk = analysis.parameters["risk_percent"]

    assert risk.total_observations == 3
    assert risk.dominant_value == 0.75
    assert risk.dominant_count == 3
    assert risk.dominant_rate == 100.0


def test_analyzer_preserves_frequency_order_by_first_appearance():
    analysis = ParameterStabilityAnalyzer().analyze(
        report=build_report(),
    )

    assert list(
        analysis.parameters[
            "rsi_period"
        ].frequencies.keys()
    ) == [
        10,
        14,
        21,
    ]
