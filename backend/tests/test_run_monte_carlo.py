from pathlib import Path

import pytest

from backend.backtesting.run_monte_carlo import main


def test_run_monte_carlo_requires_file_argument():
    with pytest.raises(
        SystemExit,
        match="Uso:",
    ):
        main([])


def test_run_monte_carlo_rejects_missing_file():
    with pytest.raises(
        FileNotFoundError,
        match="No existe el archivo",
    ):
        main(["data/reports/missing.csv"])


def test_run_monte_carlo_runs_analysis(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "trade_journal.csv"

    file_path.write_text(
        "pnl\n10.0\n-5.0\n20.0\n",
        encoding="utf-8",
    )

    captured = {}

    class DummyResult:
        pass

    class DummyEngine:
        def __init__(
            self,
            simulations,
            seed=None,
        ):
            captured["simulations"] = simulations
            captured["seed"] = seed

        def run(
            self,
            pnls,
            initial_balance,
        ):
            captured["pnls"] = pnls
            captured["initial_balance"] = initial_balance
            return DummyResult()

    class DummyReport:
        total_simulations = 100
        average_final_balance = 1025.0
        median_final_balance = 1025.0
        best_final_balance = 1025.0
        worst_final_balance = 1025.0
        average_max_drawdown = 5.0
        worst_max_drawdown = 10.0
        loss_probability = 0.0
        ruin_probability = 0.0

    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloEngine",
        DummyEngine,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloReport.from_result",
        lambda result, ruin_balance: DummyReport(),
    )

    class DummyJsonExporter:
        def export_json(
            self,
            report,
            file_path,
        ):
            captured["json_path"] = file_path

    class DummyCsvExporter:
        def export_csv(
            self,
            report,
            file_path,
        ):
            captured["csv_path"] = file_path

    class DummyDashboardExporter:
        def export_html(
            self,
            report,
            file_path,
        ):
            captured["dashboard_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloJsonExporter",
        DummyJsonExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloCsvExporter",
        DummyCsvExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloDashboardExporter",
        DummyDashboardExporter,
    )

    main(
        [
            str(file_path),
            "--simulations",
            "100",
            "--initial-balance",
            "1000",
            "--ruin-balance",
            "500",
            "--seed",
            "42",
        ]
    )

    assert captured["simulations"] == 100
    assert captured["seed"] == 42
    assert captured["pnls"] == [
        10.0,
        -5.0,
        20.0,
    ]
    assert captured["initial_balance"] == 1000.0


def test_run_monte_carlo_uses_default_paths(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "trade_journal.csv"

    file_path.write_text(
        "pnl\n10.0\n",
        encoding="utf-8",
    )

    captured = {}

    class DummyEngine:
        def __init__(
            self,
            simulations,
            seed=None,
        ):
            pass

        def run(
            self,
            pnls,
            initial_balance,
        ):
            return object()

    class DummyReport:
        total_simulations = 1
        average_final_balance = 1010.0
        median_final_balance = 1010.0
        best_final_balance = 1010.0
        worst_final_balance = 1010.0
        average_max_drawdown = 0.0
        worst_max_drawdown = 0.0
        loss_probability = 0.0
        ruin_probability = 0.0

    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloEngine",
        DummyEngine,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloReport.from_result",
        lambda result, ruin_balance: DummyReport(),
    )

    class DummyJsonExporter:
        def export_json(
            self,
            report,
            file_path,
        ):
            captured["json_path"] = file_path

    class DummyCsvExporter:
        def export_csv(
            self,
            report,
            file_path,
        ):
            captured["csv_path"] = file_path

    class DummyDashboardExporter:
        def export_html(
            self,
            report,
            file_path,
        ):
            captured["dashboard_path"] = file_path

    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloJsonExporter",
        DummyJsonExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloCsvExporter",
        DummyCsvExporter,
    )
    monkeypatch.setattr(
        "backend.backtesting.run_monte_carlo.MonteCarloDashboardExporter",
        DummyDashboardExporter,
    )

    main([str(file_path)])

    assert str(
        captured["json_path"]
    ).replace("\\", "/") == (
        "data/reports/monte_carlo.json"
    )

    assert str(
        captured["csv_path"]
    ).replace("\\", "/") == (
        "data/reports/monte_carlo_summary.csv"
    )

    assert str(
        captured["dashboard_path"]
    ).replace("\\", "/") == (
        "data/reports/monte_carlo_dashboard.html"
    )


def test_run_monte_carlo_rejects_missing_pnl_column(
    tmp_path,
):
    file_path = tmp_path / "trade_journal.csv"

    file_path.write_text(
        "result\nWIN\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="pnl",
    ):
        main([str(file_path)])
