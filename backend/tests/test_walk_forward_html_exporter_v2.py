import pytest

from backend.backtesting.walk_forward_html_exporter_v2 import (
    WalkForwardHtmlExporterV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)
from backend.backtesting.walk_forward_report_v2 import (
    WalkForwardReportV2,
)


def build_report():

    result = WalkForwardOptimizationResultV2(
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
                    "stop_loss": 20,
                    "take_profit": 60,
                },
            },
            {
                "window_index": 1,
                "success": True,
                "training_score": 87.0,
                "testing_score": 76.0,
                "testing_net_pnl": 150.0,
                "testing_win_rate": 0.54,
                "testing_maximum_drawdown": 170.0,
                "best_parameters": {
                    "ema": 50,
                    "stop_loss": 20,
                    "take_profit": 60,
                },
            },
        ],
    )

    return WalkForwardReportV2(
        optimization_result=result,
    )


def test_exports_html_report(tmp_path):

    output_path = (
        tmp_path
        / "reports"
        / "walk_forward.html"
    )

    exporter = WalkForwardHtmlExporterV2()

    result = exporter.export(
        report=build_report(),
        output_path=output_path,
    )

    assert result == output_path

    assert output_path.exists()

    html = output_path.read_text(
        encoding="utf-8",
    )

    assert "<html" in html.lower()
    assert "Walk Forward Report" in html
    assert "Summary" in html
    assert "Best Window" in html
    assert "Worst Window" in html
    assert "Window Results" in html


def test_creates_parent_directories(tmp_path):

    output_path = (
        tmp_path
        / "nested"
        / "reports"
        / "report.html"
    )

    WalkForwardHtmlExporterV2().export(
        report=build_report(),
        output_path=output_path,
    )

    assert output_path.exists()


def test_rejects_invalid_report(tmp_path):

    exporter = WalkForwardHtmlExporterV2()

    with pytest.raises(TypeError):

        exporter.export(
            report={},
            output_path=(
                tmp_path
                / "report.html"
            ),
        )


def test_rejects_directory_output(tmp_path):

    exporter = WalkForwardHtmlExporterV2()

    with pytest.raises(ValueError):

        exporter.export(
            report=build_report(),
            output_path=tmp_path,
        )


def test_export_does_not_modify_report(tmp_path):

    report = build_report()

    original = report.to_dict()

    WalkForwardHtmlExporterV2().export(
        report=report,
        output_path=(
            tmp_path
            / "report.html"
        ),
    )

    assert report.to_dict() == original
