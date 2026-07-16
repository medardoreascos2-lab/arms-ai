import json

from backend.backtesting.monte_carlo_json_exporter import (
    MonteCarloJsonExporter,
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


def test_monte_carlo_json_exporter_writes_json(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.json"

    returned_path = MonteCarloJsonExporter().export_json(
        report=build_report(),
        file_path=file_path,
    )

    assert returned_path == file_path
    assert file_path.exists()

    data = json.loads(
        file_path.read_text(
            encoding="utf-8",
        )
    )

    assert data["total_simulations"] == 1000
    assert data["average_final_balance"] == 11250.0
    assert data["median_final_balance"] == 11180.0
    assert data["best_final_balance"] == 13800.0
    assert data["worst_final_balance"] == 8700.0

    assert data["average_max_drawdown"] == 950.0
    assert data["worst_max_drawdown"] == 2400.0

    assert data["loss_probability"] == 7.5
    assert data["ruin_probability"] == 1.2

    assert (
        data["final_balance_percentiles"]["5"]
        == 9400.0
    )
    assert (
        data["final_balance_percentiles"]["50"]
        == 11180.0
    )
    assert (
        data["final_balance_percentiles"]["95"]
        == 12950.0
    )

    assert (
        data["drawdown_percentiles"]["50"]
        == 880.0
    )
    assert (
        data["drawdown_percentiles"]["95"]
        == 1850.0
    )
    assert (
        data["drawdown_percentiles"]["99"]
        == 2200.0
    )


def test_monte_carlo_json_exporter_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "monte_carlo.json"
    )

    MonteCarloJsonExporter().export_json(
        report=build_report(),
        file_path=file_path,
    )

    assert file_path.exists()


def test_monte_carlo_json_exporter_uses_pretty_format(
    tmp_path,
):
    file_path = tmp_path / "monte_carlo.json"

    MonteCarloJsonExporter().export_json(
        report=build_report(),
        file_path=file_path,
    )

    content = file_path.read_text(
        encoding="utf-8",
    )

    assert "\n" in content
    assert '  "total_simulations"' in content
