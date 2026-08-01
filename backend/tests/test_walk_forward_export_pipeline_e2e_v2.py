import json

from backend.backtesting.walk_forward_html_exporter_v2 import (
    WalkForwardHtmlExporterV2,
)
from backend.backtesting.walk_forward_json_exporter_v2 import (
    WalkForwardJsonExporterV2,
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
                "training_score": 92.0,
                "testing_score": 84.0,
                "testing_net_pnl": 510.0,
                "testing_win_rate": 0.68,
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
                "training_score": 89.0,
                "testing_score": 80.0,
                "testing_net_pnl": 240.0,
                "testing_win_rate": 0.60,
                "testing_maximum_drawdown": 145.0,
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


def test_walk_forward_export_pipeline(tmp_path):

    report = build_report()

    output_directory = (
        tmp_path
        / "walk_forward"
    )

    json_path = (
        output_directory
        / "walk_forward.json"
    )

    html_path = (
        output_directory
        / "walk_forward.html"
    )

    WalkForwardJsonExporterV2().export(
        report=report,
        output_path=json_path,
    )

    WalkForwardHtmlExporterV2().export(
        report=report,
        output_path=html_path,
    )

    assert json_path.exists()
    assert html_path.exists()

    payload = json.loads(
        json_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["summary"][
        "total_windows"
    ] == 2

    html = html_path.read_text(
        encoding="utf-8",
    )

    assert "Walk Forward Report" in html
    assert "Summary" in html
    assert "Best Window" in html
    assert "Worst Window" in html
    assert "Window Results" in html
