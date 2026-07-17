from datetime import datetime, timedelta, timezone

from backend.portfolio.portfolio import Portfolio
from backend.portfolio.portfolio_dashboard_exporter import (
    PortfolioDashboardExporter,
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
                ],
            ),
            cash=900,
        ),
    ]

    return PortfolioReport.from_snapshots(
        snapshots=snapshots,
    )


def test_dashboard_exporter_creates_html(
    tmp_path,
):
    html = tmp_path / "portfolio_dashboard.html"

    exporter = PortfolioDashboardExporter()

    returned = exporter.export_dashboard(
        report=build_report(),
        file_path=html,
    )

    assert returned == html
    assert html.exists()


def test_dashboard_contains_metrics(
    tmp_path,
):
    html = tmp_path / "dashboard.html"

    PortfolioDashboardExporter().export_dashboard(
        report=build_report(),
        file_path=html,
    )

    content = html.read_text(
        encoding="utf-8",
    )

    assert "Portfolio Dashboard" in content

    assert "Initial Equity" in content
    assert "Final Equity" in content
    assert "Net Profit" in content
    assert "Return %" in content

    assert "Peak Equity" in content
    assert "Max Drawdown" in content

    assert "Average Gross Exposure" in content
    assert "Max Gross Exposure" in content

    assert "Snapshots" in content
    assert "2026-07-16T12:00:00+00:00" in content
    assert "1240.0" in content


def test_dashboard_creates_parent_directory(
    tmp_path,
):
    html = (
        tmp_path
        / "reports"
        / "portfolio_dashboard.html"
    )

    PortfolioDashboardExporter().export_dashboard(
        report=build_report(),
        file_path=html,
    )

    assert html.exists()
