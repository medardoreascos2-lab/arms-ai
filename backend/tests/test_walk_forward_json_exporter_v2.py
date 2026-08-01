import json

import pytest

from backend.backtesting.walk_forward_json_exporter_v2 import (
    WalkForwardJsonExporterV2,
)
from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)
from backend.backtesting.walk_forward_report_v2 import (
    WalkForwardReportV2,
)


def build_report() -> WalkForwardReportV2:

    result = WalkForwardOptimizationResultV2(
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
                    "stop_loss": 20,
                    "take_profit": 60,
                },
            },
            {
                "window_index": 1,
                "success": True,
                "training_score": 88.0,
                "testing_score": 78.0,
                "testing_net_pnl": 150.0,
                "testing_win_rate": 0.55,
                "testing_maximum_drawdown": 160.0,
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


def test_exports_walk_forward_report_to_json(
    tmp_path,
):

    output_path = (
        tmp_path
        / "reports"
        / "walk_forward.json"
    )

    exporter = WalkForwardJsonExporterV2()

    result = exporter.export(
        report=build_report(),
        output_path=output_path,
    )

    assert result == output_path
    assert output_path.exists()
    assert output_path.is_file()

    payload = json.loads(
        output_path.read_text(
            encoding="utf-8",
        )
    )

    assert payload["summary"] == {
        "total_windows": 2,
        "successful_windows": 2,
        "failed_windows": 0,
        "average_training_score": 89.0,
        "average_testing_score": 80.0,
        "average_testing_net_pnl": 225.0,
        "average_testing_win_rate": pytest.approx(
            0.575
        ),
        "average_testing_maximum_drawdown": 140.0,
        "most_frequent_parameters": {
            "ema": 50,
            "stop_loss": 20,
            "take_profit": 60,
        },
    }

    assert payload["best_window"][
        "window_index"
    ] == 0

    assert payload["worst_window"][
        "window_index"
    ] == 1

    assert len(
        payload["window_results"]
    ) == 2


def test_creates_parent_directories(
    tmp_path,
):

    output_path = (
        tmp_path
        / "nested"
        / "reports"
        / "result.json"
    )

    WalkForwardJsonExporterV2().export(
        report=build_report(),
        output_path=output_path,
    )

    assert output_path.exists()


def test_uses_readable_indented_json(
    tmp_path,
):

    output_path = (
        tmp_path
        / "walk_forward.json"
    )

    exporter = WalkForwardJsonExporterV2(
        indent=2,
    )

    exporter.export(
        report=build_report(),
        output_path=output_path,
    )

    content = output_path.read_text(
        encoding="utf-8",
    )

    assert "\n" in content
    assert '  "summary"' in content


def test_rejects_invalid_report(
    tmp_path,
):

    exporter = WalkForwardJsonExporterV2()

    with pytest.raises(
        TypeError,
        match="WalkForwardReportV2",
    ):
        exporter.export(
            report={},
            output_path=(
                tmp_path
                / "report.json"
            ),
        )


def test_rejects_directory_as_output_path(
    tmp_path,
):

    exporter = WalkForwardJsonExporterV2()

    with pytest.raises(
        ValueError,
        match="output_path",
    ):
        exporter.export(
            report=build_report(),
            output_path=tmp_path,
        )


def test_export_does_not_modify_report(
    tmp_path,
):

    report = build_report()

    original = report.to_dict()

    WalkForwardJsonExporterV2().export(
        report=report,
        output_path=(
            tmp_path
            / "report.json"
        ),
    )

    assert report.to_dict() == original


@pytest.mark.parametrize(
    "indent",
    [
        -1,
        "2",
    ],
)
def test_rejects_invalid_indent(
    indent,
):

    with pytest.raises(
        (
            TypeError,
            ValueError,
        ),
    ):
        WalkForwardJsonExporterV2(
            indent=indent,
        )
