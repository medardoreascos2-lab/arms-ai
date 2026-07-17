from pathlib import Path

import pytest

from backend.portfolio.run_portfolio import (
    main,
)


def test_run_portfolio_requires_file_argument():
    with pytest.raises(
        SystemExit,
        match="Uso:",
    ):
        main([])


def test_run_portfolio_rejects_missing_file():
    with pytest.raises(
        FileNotFoundError,
        match="No existe el archivo",
    ):
        main(
            [
                "data/reports/"
                "missing_portfolio.csv",
            ]
        )


def test_run_portfolio_runs_analysis(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "portfolio.csv"

    file_path.write_text(
        (
            "timestamp,cash,symbol,quantity,"
            "average_price,current_price\n"
            "2026-07-16T12:00:00+00:00,"
            "1000.0,,,,\n"
            "2026-07-16T12:01:00+00:00,"
            "900.0,NQ,2,100,110\n"
            "2026-07-16T12:01:00+00:00,"
            "900.0,ES,-3,50,40\n"
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyReport:
        total_snapshots = 2
        initial_equity = 1000.0
        final_equity = 1240.0
        net_profit = 240.0
        return_percent = 24.0
        peak_equity = 1240.0
        max_drawdown = 0.0
        max_drawdown_percent = 0.0
        average_gross_exposure = 170.0
        max_gross_exposure = 340.0
        average_net_exposure = 50.0
        max_net_exposure = 100.0
        min_net_exposure = 0.0

    def dummy_build_report(file_path):
        captured["source_file"] = file_path
        return DummyReport()

    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "build_report_from_csv",
        dummy_build_report,
    )

    class DummyJsonExporter:
        def export_json(
            self,
            *,
            report,
            file_path,
        ):
            captured["json"] = file_path

    class DummyCsvExporter:
        def export_csv(
            self,
            *,
            report,
            summary_file,
            snapshots_file,
        ):
            captured["summary"] = summary_file
            captured["snapshots"] = snapshots_file

    class DummyDashboardExporter:
        def export_dashboard(
            self,
            *,
            report,
            file_path,
        ):
            captured["dashboard"] = file_path

    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "PortfolioJsonExporter",
        DummyJsonExporter,
    )
    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "PortfolioCsvExporter",
        DummyCsvExporter,
    )
    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "PortfolioDashboardExporter",
        DummyDashboardExporter,
    )

    main([str(file_path)])

    assert captured["source_file"] == file_path

    assert str(
        captured["json"]
    ).replace("\\", "/") == (
        "data/reports/portfolio.json"
    )

    assert str(
        captured["summary"]
    ).replace("\\", "/") == (
        "data/reports/portfolio_summary.csv"
    )

    assert str(
        captured["snapshots"]
    ).replace("\\", "/") == (
        "data/reports/portfolio_snapshots.csv"
    )

    assert str(
        captured["dashboard"]
    ).replace("\\", "/") == (
        "data/reports/portfolio_dashboard.html"
    )


def test_run_portfolio_supports_custom_paths(
    tmp_path,
    monkeypatch,
):
    file_path = tmp_path / "portfolio.csv"

    file_path.write_text(
        (
            "timestamp,cash,symbol,quantity,"
            "average_price,current_price\n"
            "2026-07-16T12:00:00+00:00,"
            "1000.0,,,,\n"
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyReport:
        total_snapshots = 1
        initial_equity = 1000.0
        final_equity = 1000.0
        net_profit = 0.0
        return_percent = 0.0
        peak_equity = 1000.0
        max_drawdown = 0.0
        max_drawdown_percent = 0.0
        average_gross_exposure = 0.0
        max_gross_exposure = 0.0
        average_net_exposure = 0.0
        max_net_exposure = 0.0
        min_net_exposure = 0.0

    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "build_report_from_csv",
        lambda file_path: DummyReport(),
    )

    class DummyJsonExporter:
        def export_json(
            self,
            *,
            report,
            file_path,
        ):
            captured["json"] = file_path

    class DummyCsvExporter:
        def export_csv(
            self,
            *,
            report,
            summary_file,
            snapshots_file,
        ):
            captured["summary"] = summary_file
            captured["snapshots"] = snapshots_file

    class DummyDashboardExporter:
        def export_dashboard(
            self,
            *,
            report,
            file_path,
        ):
            captured["dashboard"] = file_path

    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "PortfolioJsonExporter",
        DummyJsonExporter,
    )
    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "PortfolioCsvExporter",
        DummyCsvExporter,
    )
    monkeypatch.setattr(
        "backend.portfolio.run_portfolio."
        "PortfolioDashboardExporter",
        DummyDashboardExporter,
    )

    main(
        [
            str(file_path),
            "--json",
            "custom/portfolio.json",
            "--summary",
            "custom/summary.csv",
            "--snapshots",
            "custom/snapshots.csv",
            "--dashboard",
            "custom/dashboard.html",
        ]
    )

    assert captured["json"] == Path(
        "custom/portfolio.json"
    )
    assert captured["summary"] == Path(
        "custom/summary.csv"
    )
    assert captured["snapshots"] == Path(
        "custom/snapshots.csv"
    )
    assert captured["dashboard"] == Path(
        "custom/dashboard.html"
    )


def test_build_report_from_csv_rejects_missing_columns(
    tmp_path,
):
    file_path = tmp_path / "portfolio.csv"

    file_path.write_text(
        "timestamp,cash\n",
        encoding="utf-8",
    )

    from backend.portfolio.run_portfolio import (
        build_report_from_csv,
    )

    with pytest.raises(
        ValueError,
        match="columnas",
    ):
        build_report_from_csv(
            file_path=file_path,
        )
