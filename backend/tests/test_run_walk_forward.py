from pathlib import Path

import pytest

from backend.backtesting.run_walk_forward import main


def test_run_walk_forward_requires_file_argument():
    with pytest.raises(
        SystemExit,
        match="Uso:",
    ):
        main([])


def test_run_walk_forward_rejects_missing_file():
    with pytest.raises(
        FileNotFoundError,
        match="No existe el archivo",
    ):
        main(["data/missing.csv"])


def test_run_walk_forward_runs_analysis(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        (
            "timestamp,symbol,timeframe,open,high,"
            "low,close,volume\n"
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyReport:
        total_windows = 3
        profitable_windows = 2
        losing_windows = 1
        breakeven_windows = 0

        total_net_profit = 25.0
        average_net_profit = 8.33
        profitable_window_rate = 66.67
        stability_score = 71.5

    class DummyRunner:
        def run_from_csv(self, file_path):
            captured["source_file"] = file_path
            return DummyReport()

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.build_runner",
        lambda settings, training_size, testing_size, step_size: (
            DummyRunner()
        ),
    )

    class DummyCsvExporter:
        def export_csv(
            self,
            report,
            file_path,
            summary_path=None,
        ):
            pass

    class DummyJsonExporter:
        def export_json(
            self,
            report,
            file_path,
        ):
            pass

    class DummyDashboardExporter:
        def export_html(
            self,
            report,
            file_path,
        ):
            pass

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardCsvExporter",
        DummyCsvExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardJsonExporter",
        DummyJsonExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardDashboardExporter",
        DummyDashboardExporter,
    )

    main([str(file_path)])

    assert captured["source_file"] == file_path


def test_run_walk_forward_exports_reports(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"
    windows_path = tmp_path / "reports" / "windows.csv"
    summary_path = tmp_path / "reports" / "summary.csv"
    json_path = tmp_path / "reports" / "walk_forward.json"
    dashboard_path = tmp_path / "reports" / "dashboard.html"

    file_path.write_text(
        (
            "timestamp,symbol,timeframe,open,high,"
            "low,close,volume\n"
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyReport:
        total_windows = 1
        profitable_windows = 1
        losing_windows = 0
        breakeven_windows = 0

        total_net_profit = 10.0
        average_net_profit = 10.0
        profitable_window_rate = 100.0
        stability_score = 100.0

    class DummyRunner:
        def run_from_csv(self, file_path):
            return DummyReport()

    class DummyCsvExporter:
        def export_csv(
            self,
            report,
            file_path,
            summary_path=None,
        ):
            captured["windows_path"] = file_path
            captured["summary_path"] = summary_path

    class DummyJsonExporter:
        def export_json(
            self,
            report,
            file_path,
        ):
            captured["json_path"] = file_path

    class DummyDashboardExporter:
        def export_html(
            self,
            report,
            file_path,
        ):
            captured["dashboard_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.build_runner",
        lambda settings, training_size, testing_size, step_size: (
            DummyRunner()
        ),
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardCsvExporter",
        DummyCsvExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardJsonExporter",
        DummyJsonExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardDashboardExporter",
        DummyDashboardExporter,
    )

    main(
        [
            str(file_path),
            "--windows",
            str(windows_path),
            "--summary",
            str(summary_path),
            "--json",
            str(json_path),
            "--dashboard",
            str(dashboard_path),
        ]
    )

    assert captured["windows_path"] == windows_path
    assert captured["summary_path"] == summary_path
    assert captured["json_path"] == json_path
    assert captured["dashboard_path"] == dashboard_path


def test_run_walk_forward_uses_default_paths(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "candles.csv"

    file_path.write_text(
        (
            "timestamp,symbol,timeframe,open,high,"
            "low,close,volume\n"
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyReport:
        total_windows = 0
        profitable_windows = 0
        losing_windows = 0
        breakeven_windows = 0

        total_net_profit = 0.0
        average_net_profit = 0.0
        profitable_window_rate = 0.0
        stability_score = 0.0

    class DummyRunner:
        def run_from_csv(self, file_path):
            return DummyReport()

    class DummyCsvExporter:
        def export_csv(
            self,
            report,
            file_path,
            summary_path=None,
        ):
            captured["windows_path"] = file_path
            captured["summary_path"] = summary_path

    class DummyJsonExporter:
        def export_json(self, report, file_path):
            captured["json_path"] = file_path

    class DummyDashboardExporter:
        def export_html(self, report, file_path):
            captured["dashboard_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.build_runner",
        lambda settings, training_size, testing_size, step_size: (
            DummyRunner()
        ),
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardCsvExporter",
        DummyCsvExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardJsonExporter",
        DummyJsonExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward.WalkForwardDashboardExporter",
        DummyDashboardExporter,
    )

    main([str(file_path)])

    assert str(
        captured["windows_path"]
    ).replace("\\", "/") == (
        "data/reports/walk_forward_windows.csv"
    )

    assert str(
        captured["summary_path"]
    ).replace("\\", "/") == (
        "data/reports/walk_forward_summary.csv"
    )

    assert str(
        captured["json_path"]
    ).replace("\\", "/") == (
        "data/reports/walk_forward.json"
    )

    assert str(
        captured["dashboard_path"]
    ).replace("\\", "/") == (
        "data/reports/walk_forward_dashboard.html"
    )
