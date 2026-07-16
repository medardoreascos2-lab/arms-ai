from pathlib import Path

import pytest

from backend.backtesting.run_walk_forward_optimization import (
    main,
)


def test_requires_csv_argument():
    with pytest.raises(SystemExit):
        main([])


def test_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        main(
            [
                str(
                    tmp_path / "missing.csv"
                )
            ]
        )


def test_runner_is_called(
    tmp_path,
    monkeypatch,
):
    csv_file = tmp_path / "candles.csv"

    csv_file.write_text(
        (
            "timestamp,symbol,timeframe,"
            "open,high,low,close,volume\n"
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyReport:
        total_windows = 1
        profitable_testing_windows = 1
        losing_testing_windows = 0

        total_training_net_profit = 20.0
        total_testing_net_profit = 10.0

        testing_profitable_rate = 100.0

        overfit_windows = 0
        overfit_rate = 0.0

    class DummyRunner:
        def run_from_csv(
            self,
            file_path,
        ):
            captured["file_path"] = file_path
            return DummyReport()

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward_optimization.build_runner",
        lambda **kwargs: DummyRunner(),
    )

    class DummyCsvExporter:
        def export_csv(
            self,
            report,
            file_path,
            summary_path=None,
        ):
            captured["csv"] = file_path
            captured["summary"] = summary_path

    class DummyJsonExporter:
        def export_json(
            self,
            report,
            file_path,
        ):
            captured["json"] = file_path

    class DummyDashboardExporter:
        def export_html(
            self,
            report,
            file_path,
        ):
            captured["html"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward_optimization."
        "WalkForwardOptimizationCsvExporter",
        DummyCsvExporter,
    )

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward_optimization."
        "WalkForwardOptimizationJsonExporter",
        DummyJsonExporter,
    )

    monkeypatch.setattr(
        "backend.backtesting.run_walk_forward_optimization."
        "WalkForwardOptimizationDashboardExporter",
        DummyDashboardExporter,
    )

    main(
        [
            str(csv_file),
        ]
    )

    assert captured["file_path"] == csv_file

    assert str(
        captured["csv"]
    ).replace("\\", "/").endswith(
        "walk_forward_optimization_windows.csv"
    )

    assert str(
        captured["summary"]
    ).replace("\\", "/").endswith(
        "walk_forward_optimization_summary.csv"
    )

    assert str(
        captured["json"]
    ).replace("\\", "/").endswith(
        "walk_forward_optimization.json"
    )

    assert str(
        captured["html"]
    ).replace("\\", "/").endswith(
        "walk_forward_optimization_dashboard.html"
    )
