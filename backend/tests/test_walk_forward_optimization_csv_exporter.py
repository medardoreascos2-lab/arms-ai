import csv
import json

from backend.backtesting.walk_forward_optimization_csv_exporter import (
    WalkForwardOptimizationCsvExporter,
)
from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
    WalkForwardOptimizationWindowReport,
)


def build_report() -> WalkForwardOptimizationReport:
    return WalkForwardOptimizationReport(
        total_windows=2,
        profitable_testing_windows=1,
        losing_testing_windows=1,
        breakeven_testing_windows=0,
        total_training_net_profit=180.0,
        total_testing_net_profit=30.0,
        average_training_net_profit=90.0,
        average_testing_net_profit=15.0,
        average_performance_degradation=75.0,
        testing_profitable_rate=50.0,
        overfit_windows=1,
        overfit_rate=50.0,
        windows=[
            WalkForwardOptimizationWindowReport(
                window_number=1,
                selected_parameters={
                    "ema_period": 20,
                    "rsi_period": 14,
                },
                training_net_profit=100.0,
                testing_net_profit=40.0,
                performance_degradation=60.0,
                degradation_rate=60.0,
                overfit_suspected=False,
            ),
            WalkForwardOptimizationWindowReport(
                window_number=2,
                selected_parameters={
                    "ema_period": 50,
                    "rsi_period": 21,
                },
                training_net_profit=80.0,
                testing_net_profit=-10.0,
                performance_degradation=90.0,
                degradation_rate=112.5,
                overfit_suspected=True,
            ),
        ],
    )


def test_optimization_csv_exporter_writes_windows(
    tmp_path,
):
    file_path = (
        tmp_path
        / "optimization_windows.csv"
    )

    returned_path = (
        WalkForwardOptimizationCsvExporter()
        .export_csv(
            report=build_report(),
            file_path=file_path,
        )
    )

    assert returned_path == file_path
    assert file_path.exists()

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 2

    first = rows[0]

    assert first["window_number"] == "1"
    assert json.loads(
        first["selected_parameters"]
    ) == {
        "ema_period": 20,
        "rsi_period": 14,
    }
    assert float(first["training_net_profit"]) == 100.0
    assert float(first["testing_net_profit"]) == 40.0
    assert float(
        first["performance_degradation"]
    ) == 60.0
    assert float(first["degradation_rate"]) == 60.0
    assert first["overfit_suspected"] == "False"

    second = rows[1]

    assert float(second["testing_net_profit"]) == -10.0
    assert second["overfit_suspected"] == "True"


def test_optimization_csv_exporter_uses_expected_columns(
    tmp_path,
):
    file_path = tmp_path / "windows.csv"

    WalkForwardOptimizationCsvExporter().export_csv(
        report=build_report(),
        file_path=file_path,
    )

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        assert reader.fieldnames == [
            "window_number",
            "selected_parameters",
            "training_net_profit",
            "testing_net_profit",
            "performance_degradation",
            "degradation_rate",
            "overfit_suspected",
        ]


def test_optimization_csv_exporter_writes_summary(
    tmp_path,
):
    windows_path = tmp_path / "windows.csv"
    summary_path = tmp_path / "summary.csv"

    WalkForwardOptimizationCsvExporter().export_csv(
        report=build_report(),
        file_path=windows_path,
        summary_path=summary_path,
    )

    assert summary_path.exists()

    with summary_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    values = {
        row["metric"]: row["value"]
        for row in rows
    }

    assert values["total_windows"] == "2"
    assert (
        values["profitable_testing_windows"]
        == "1"
    )
    assert values["losing_testing_windows"] == "1"
    assert float(
        values["total_training_net_profit"]
    ) == 180.0
    assert float(
        values["total_testing_net_profit"]
    ) == 30.0
    assert float(
        values["average_testing_net_profit"]
    ) == 15.0
    assert float(
        values["testing_profitable_rate"]
    ) == 50.0
    assert values["overfit_windows"] == "1"
    assert float(values["overfit_rate"]) == 50.0


def test_optimization_csv_exporter_creates_directories(
    tmp_path,
):
    windows_path = (
        tmp_path
        / "reports"
        / "windows.csv"
    )
    summary_path = (
        tmp_path
        / "reports"
        / "summary.csv"
    )

    WalkForwardOptimizationCsvExporter().export_csv(
        report=build_report(),
        file_path=windows_path,
        summary_path=summary_path,
    )

    assert windows_path.exists()
    assert summary_path.exists()


def test_optimization_csv_exporter_handles_empty_report(
    tmp_path,
):
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

    file_path = tmp_path / "windows.csv"

    WalkForwardOptimizationCsvExporter().export_csv(
        report=report,
        file_path=file_path,
    )

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert rows == []
