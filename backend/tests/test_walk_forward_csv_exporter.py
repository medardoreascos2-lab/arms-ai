import csv

from backend.backtesting.walk_forward_csv_exporter import (
    WalkForwardCsvExporter,
)
from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
    WalkForwardWindowReport,
)


def build_report() -> WalkForwardReport:
    return WalkForwardReport(
        total_windows=4,
        profitable_windows=3,
        losing_windows=1,
        breakeven_windows=0,
        total_net_profit=40.0,
        average_net_profit=10.0,
        profitable_window_rate=75.0,
        net_profit_std_dev=9.35,
        stability_score=72.41,
        best_window_number=2,
        best_window_profit=20.0,
        worst_window_number=3,
        worst_window_profit=-5.0,
        windows=[
            WalkForwardWindowReport(
                window_number=1,
                training_start=0,
                training_end=100,
                testing_start=100,
                testing_end=120,
                net_profit=10.0,
            ),
            WalkForwardWindowReport(
                window_number=2,
                training_start=20,
                training_end=120,
                testing_start=120,
                testing_end=140,
                net_profit=20.0,
            ),
            WalkForwardWindowReport(
                window_number=3,
                training_start=40,
                training_end=140,
                testing_start=140,
                testing_end=160,
                net_profit=-5.0,
            ),
            WalkForwardWindowReport(
                window_number=4,
                training_start=60,
                training_end=160,
                testing_start=160,
                testing_end=180,
                net_profit=15.0,
            ),
        ],
    )


def test_walk_forward_csv_exporter_writes_windows(
    tmp_path,
):
    file_path = tmp_path / "walk_forward.csv"

    returned_path = WalkForwardCsvExporter().export_csv(
        report=build_report(),
        file_path=file_path,
    )

    assert returned_path == file_path
    assert file_path.exists()

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    assert len(rows) == 4

    assert rows[0]["window_number"] == "1"
    assert rows[0]["training_start"] == "0"
    assert rows[0]["training_end"] == "100"
    assert rows[0]["testing_start"] == "100"
    assert rows[0]["testing_end"] == "120"
    assert float(rows[0]["net_profit"]) == 10.0

    assert rows[2]["window_number"] == "3"
    assert float(rows[2]["net_profit"]) == -5.0


def test_walk_forward_csv_exporter_uses_expected_columns(
    tmp_path,
):
    file_path = tmp_path / "walk_forward.csv"

    WalkForwardCsvExporter().export_csv(
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
            "training_start",
            "training_end",
            "testing_start",
            "testing_end",
            "net_profit",
        ]


def test_walk_forward_csv_exporter_writes_summary_file(
    tmp_path,
):
    windows_path = tmp_path / "walk_forward.csv"
    summary_path = tmp_path / "walk_forward_summary.csv"

    WalkForwardCsvExporter().export_csv(
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

    assert values["total_windows"] == "4"
    assert values["profitable_windows"] == "3"
    assert values["losing_windows"] == "1"
    assert values["breakeven_windows"] == "0"
    assert float(values["total_net_profit"]) == 40.0
    assert float(values["average_net_profit"]) == 10.0
    assert float(values["profitable_window_rate"]) == 75.0
    assert float(values["stability_score"]) == 72.41
    assert values["best_window_number"] == "2"
    assert float(values["best_window_profit"]) == 20.0
    assert values["worst_window_number"] == "3"
    assert float(values["worst_window_profit"]) == -5.0


def test_walk_forward_csv_exporter_creates_parent_directories(
    tmp_path,
):
    windows_path = (
        tmp_path
        / "reports"
        / "walk_forward.csv"
    )
    summary_path = (
        tmp_path
        / "reports"
        / "walk_forward_summary.csv"
    )

    WalkForwardCsvExporter().export_csv(
        report=build_report(),
        file_path=windows_path,
        summary_path=summary_path,
    )

    assert windows_path.exists()
    assert summary_path.exists()


def test_walk_forward_csv_exporter_handles_empty_report(
    tmp_path,
):
    report = WalkForwardReport(
        total_windows=0,
        profitable_windows=0,
        losing_windows=0,
        breakeven_windows=0,
        total_net_profit=0.0,
        average_net_profit=0.0,
        profitable_window_rate=0.0,
        net_profit_std_dev=0.0,
        stability_score=0.0,
        best_window_number=None,
        best_window_profit=None,
        worst_window_number=None,
        worst_window_profit=None,
        windows=[],
    )

    file_path = tmp_path / "walk_forward.csv"

    WalkForwardCsvExporter().export_csv(
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
