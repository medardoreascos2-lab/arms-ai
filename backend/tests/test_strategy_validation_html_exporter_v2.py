import pytest

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)
from backend.backtesting.monte_carlo_simulator_v2 import (
    MonteCarloSimulationResultV2,
)
from backend.backtesting.strategy_validation_html_exporter_v2 import (
    StrategyValidationHtmlExporterV2,
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


def build_report() -> StrategyValidationReportV2:

    walk_forward_result = (
        WalkForwardOptimizationResultV2(
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
    )

    monte_carlo_report = MonteCarloReportV2(
        simulation_result=(
            MonteCarloSimulationResultV2(
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
        ),
    )

    validation_result = (
        StrategyValidationResultV2(
            backtest_score=90.0,
            walk_forward_result=(
                walk_forward_result
            ),
            monte_carlo_report=(
                monte_carlo_report
            ),
        )
    )

    return StrategyValidationReportV2(
        validation_result=validation_result,
    )


def test_exports_strategy_validation_report_to_html(
    tmp_path,
):

    output_path = (
        tmp_path
        / "reports"
        / "strategy_validation.html"
    )

    result = (
        StrategyValidationHtmlExporterV2()
        .export(
            report=build_report(),
            output_path=output_path,
        )
    )

    assert result == output_path
    assert output_path.exists()
    assert output_path.is_file()

    html = output_path.read_text(
        encoding="utf-8",
    )

    assert "<html" in html.lower()
    assert "Strategy Validation Report" in html
    assert "Summary" in html
    assert "Backtest Score" in html
    assert "Walk Forward" in html
    assert "Monte Carlo" in html
    assert "Validation Score" in html


def test_creates_parent_directories(
    tmp_path,
):

    output_path = (
        tmp_path
        / "nested"
        / "reports"
        / "validation.html"
    )

    StrategyValidationHtmlExporterV2().export(
        report=build_report(),
        output_path=output_path,
    )

    assert output_path.exists()


def test_rejects_invalid_report(
    tmp_path,
):

    with pytest.raises(
        TypeError,
        match="StrategyValidationReportV2",
    ):
        StrategyValidationHtmlExporterV2().export(
            report={},
            output_path=(
                tmp_path
                / "validation.html"
            ),
        )


def test_rejects_directory_output(
    tmp_path,
):

    with pytest.raises(
        ValueError,
        match="output_path",
    ):
        StrategyValidationHtmlExporterV2().export(
            report=build_report(),
            output_path=tmp_path,
        )


def test_export_does_not_modify_report(
    tmp_path,
):

    report = build_report()
    original = report.to_dict()

    StrategyValidationHtmlExporterV2().export(
        report=report,
        output_path=(
            tmp_path
            / "validation.html"
        ),
    )

    assert report.to_dict() == original
