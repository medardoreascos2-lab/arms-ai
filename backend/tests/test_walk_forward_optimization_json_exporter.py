import json

from backend.backtesting.walk_forward_optimization_json_exporter import (
    WalkForwardOptimizationJsonExporter,
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


def test_optimization_json_exporter_writes_json(
    tmp_path,
):
    file_path = (
        tmp_path
        / "walk_forward_optimization.json"
    )

    returned_path = (
        WalkForwardOptimizationJsonExporter()
        .export_json(
            report=build_report(),
            file_path=file_path,
        )
    )

    assert returned_path == file_path
    assert file_path.exists()

    data = json.loads(
        file_path.read_text(
            encoding="utf-8",
        )
    )

    assert data["summary"]["total_windows"] == 2
    assert (
        data["summary"]["profitable_testing_windows"]
        == 1
    )
    assert data["summary"]["overfit_windows"] == 1
    assert data["summary"]["overfit_rate"] == 50.0

    assert len(data["windows"]) == 2

    first = data["windows"][0]

    assert first["window_number"] == 1
    assert first["selected_parameters"] == {
        "ema_period": 20,
        "rsi_period": 14,
    }
    assert first["training_net_profit"] == 100.0
    assert first["testing_net_profit"] == 40.0
    assert first["performance_degradation"] == 60.0
    assert first["degradation_rate"] == 60.0
    assert first["overfit_suspected"] is False

    second = data["windows"][1]

    assert second["testing_net_profit"] == -10.0
    assert second["overfit_suspected"] is True


def test_optimization_json_exporter_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "optimization.json"
    )

    WalkForwardOptimizationJsonExporter().export_json(
        report=build_report(),
        file_path=file_path,
    )

    assert file_path.exists()


def test_optimization_json_exporter_handles_empty_report(
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

    file_path = tmp_path / "optimization.json"

    WalkForwardOptimizationJsonExporter().export_json(
        report=report,
        file_path=file_path,
    )

    data = json.loads(
        file_path.read_text(
            encoding="utf-8",
        )
    )

    assert data["summary"]["total_windows"] == 0
    assert data["summary"]["overfit_rate"] == 0.0
    assert data["windows"] == []


def test_optimization_json_exporter_preserves_unicode(
    tmp_path,
):
    report = build_report()

    report.windows[0].selected_parameters[
        "descripción"
    ] = "configuración rápida"

    file_path = tmp_path / "optimization.json"

    WalkForwardOptimizationJsonExporter().export_json(
        report=report,
        file_path=file_path,
    )

    content = file_path.read_text(
        encoding="utf-8",
    )

    assert "descripción" in content
    assert "configuración rápida" in content
