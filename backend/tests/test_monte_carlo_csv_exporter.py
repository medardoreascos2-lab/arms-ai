import csv

from backend.backtesting.monte_carlo_csv_exporter import (
    MonteCarloCsvExporter,
)
from backend.backtesting.monte_carlo_report import (
    MonteCarloReport,
)


def build_report() -> MonteCarloReport:
    return MonteCarloReport(
        total_simulations=1000,
        average_final_balance=11250.0,
        median_final_balance=11180.0,
        best_final_balance=13800.0,
        worst_final_balance=8700.0,
        average_max_drawdown=950.0,
        worst_max_drawdown=2400.0,
        loss_probability=7.5,
        ruin_probability=1.2,
        final_balance_percentile_5=9400.0,
        final_balance_percentile_50=11180.0,
        final_balance_percentile_95=12950.0,
        drawdown_percentile_50=880.0,
        drawdown_percentile_95=1850.0,
        drawdown_percentile_99=2200.0,
    )


def test_monte_carlo_csv_exporter_writes_summary(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.csv"

    returned_path = MonteCarloCsvExporter().export_csv(
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

    values = {
        row["metric"]: row["value"]
        for row in rows
    }

    assert values["total_simulations"] == "1000"
    assert float(values["average_final_balance"]) == 11250.0
    assert float(values["median_final_balance"]) == 11180.0
    assert float(values["best_final_balance"]) == 13800.0
    assert float(values["worst_final_balance"]) == 8700.0

    assert float(values["average_max_drawdown"]) == 950.0
    assert float(values["worst_max_drawdown"]) == 2400.0

    assert float(values["loss_probability"]) == 7.5
    assert float(values["ruin_probability"]) == 1.2


def test_monte_carlo_csv_exporter_writes_percentiles(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.csv"

    MonteCarloCsvExporter().export_csv(
        report=build_report(),
        file_path=file_path,
    )

    with file_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    values = {
        row["metric"]: row["value"]
        for row in rows
    }

    assert float(
        values["final_balance_percentile_5"]
    ) == 9400.0

    assert float(
        values["final_balance_percentile_50"]
    ) == 11180.0

    assert float(
        values["final_balance_percentile_95"]
    ) == 12950.0

    assert float(
        values["drawdown_percentile_50"]
    ) == 880.0

    assert float(
        values["drawdown_percentile_95"]
    ) == 1850.0

    assert float(
        values["drawdown_percentile_99"]
    ) == 2200.0


def test_monte_carlo_csv_exporter_uses_expected_columns(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.csv"

    MonteCarloCsvExporter().export_csv(
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
            "metric",
            "value",
        ]


def test_monte_carlo_csv_exporter_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "monte_carlo.csv"
    )

    MonteCarloCsvExporter().export_csv(
        report=build_report(),
        file_path=file_path,
    )

    assert file_path.exists()
