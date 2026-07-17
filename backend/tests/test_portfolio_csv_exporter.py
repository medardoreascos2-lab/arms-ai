import csv
from datetime import datetime, timedelta, timezone

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_csv_exporter import (
    PortfolioCsvExporter,
)
from backend.portfolio.portfolio_position import PortfolioPosition
from backend.portfolio.portfolio_report import PortfolioReport
from backend.portfolio.portfolio_snapshot import PortfolioSnapshot


def build_report():
    start = datetime(
        2026,
        7,
        16,
        12,
        0,
        tzinfo=timezone.utc,
    )

    snapshots = [
        PortfolioSnapshot(
            timestamp=start,
            portfolio=Portfolio(
                positions=[],
            ),
            cash=1000.0,
        ),
        PortfolioSnapshot(
            timestamp=start + timedelta(minutes=1),
            portfolio=Portfolio(
                positions=[
                    PortfolioPosition(
                        symbol="NQ",
                        quantity=2,
                        average_price=100,
                        current_price=110,
                    ),
                    PortfolioPosition(
                        symbol="ES",
                        quantity=-3,
                        average_price=50,
                        current_price=40,
                    ),
                ]
            ),
            cash=900,
        ),
    ]

    return PortfolioReport.from_snapshots(
        snapshots=snapshots,
    )


def test_csv_exporter_creates_summary_and_snapshots(
    tmp_path,
):
    summary = tmp_path / "summary.csv"
    snapshots = tmp_path / "snapshots.csv"

    exporter = PortfolioCsvExporter()

    exporter.export_csv(
        report=build_report(),
        summary_file=summary,
        snapshots_file=snapshots,
    )

    assert summary.exists()
    assert snapshots.exists()


def test_summary_csv_contents(
    tmp_path,
):
    summary = tmp_path / "summary.csv"
    snapshots = tmp_path / "snapshots.csv"

    PortfolioCsvExporter().export_csv(
        report=build_report(),
        summary_file=summary,
        snapshots_file=snapshots,
    )

    rows = list(
        csv.reader(
            summary.open(
                newline="",
                encoding="utf-8",
            )
        )
    )

    values = {
        row[0]: row[1]
        for row in rows[1:]
    }

    assert values["initial_equity"] == "1000.0"
    assert values["final_equity"] == "1240.0"
    assert values["net_profit"] == "240.0"
    assert values["return_percent"] == "24.0"


def test_snapshots_csv_contents(
    tmp_path,
):
    summary = tmp_path / "summary.csv"
    snapshots = tmp_path / "snapshots.csv"

    PortfolioCsvExporter().export_csv(
        report=build_report(),
        summary_file=summary,
        snapshots_file=snapshots,
    )

    rows = list(
        csv.DictReader(
            snapshots.open(
                newline="",
                encoding="utf-8",
            )
        )
    )

    assert len(rows) == 2

    assert rows[0]["equity"] == "1000.0"

    assert rows[1]["cash"] == "900.0"
    assert rows[1]["market_value"] == "340.0"
    assert rows[1]["gross_exposure"] == "340.0"
    assert rows[1]["net_exposure"] == "100.0"


def test_exporter_creates_directories(
    tmp_path,
):
    summary = (
        tmp_path
        / "reports"
        / "summary.csv"
    )

    snapshots = (
        tmp_path
        / "reports"
        / "snapshots.csv"
    )

    PortfolioCsvExporter().export_csv(
        report=build_report(),
        summary_file=summary,
        snapshots_file=snapshots,
    )

    assert summary.exists()
    assert snapshots.exists()
