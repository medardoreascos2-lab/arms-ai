import json
from datetime import datetime, timedelta, timezone

from backend.portfolio.portfolio import (
    Portfolio,
)
from backend.portfolio.portfolio_json_exporter import (
    PortfolioJsonExporter,
)
from backend.portfolio.portfolio_position import (
    PortfolioPosition,
)
from backend.portfolio.portfolio_report import (
    PortfolioReport,
)
from backend.portfolio.portfolio_snapshot import (
    PortfolioSnapshot,
)


def build_report() -> PortfolioReport:
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
                        quantity=2.0,
                        average_price=100.0,
                        current_price=110.0,
                    ),
                    PortfolioPosition(
                        symbol="ES",
                        quantity=-3.0,
                        average_price=50.0,
                        current_price=40.0,
                    ),
                ],
            ),
            cash=900.0,
        ),
    ]

    return PortfolioReport.from_snapshots(
        snapshots=snapshots,
    )


def test_portfolio_json_exporter_writes_json(
    tmp_path,
):
    file_path = tmp_path / "portfolio.json"

    returned_path = PortfolioJsonExporter().export_json(
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

    assert data["summary"]["total_snapshots"] == 2
    assert data["summary"]["initial_equity"] == 1000.0
    assert data["summary"]["final_equity"] == 1240.0
    assert data["summary"]["net_profit"] == 240.0
    assert data["summary"]["return_percent"] == 24.0

    assert data["risk"]["peak_equity"] == 1240.0
    assert data["risk"]["max_drawdown"] == 0.0
    assert data["risk"]["max_drawdown_percent"] == 0.0

    assert data["exposure"]["average_gross_exposure"] == 170.0
    assert data["exposure"]["max_gross_exposure"] == 340.0
    assert data["exposure"]["average_net_exposure"] == 50.0
    assert data["exposure"]["max_net_exposure"] == 100.0
    assert data["exposure"]["min_net_exposure"] == 0.0


def test_portfolio_json_exporter_writes_snapshots(
    tmp_path,
):
    file_path = tmp_path / "portfolio.json"

    PortfolioJsonExporter().export_json(
        report=build_report(),
        file_path=file_path,
    )

    data = json.loads(
        file_path.read_text(
            encoding="utf-8",
        )
    )

    assert len(data["snapshots"]) == 2

    first = data["snapshots"][0]

    assert first["timestamp"] == (
        "2026-07-16T12:00:00+00:00"
    )
    assert first["cash"] == 1000.0
    assert first["equity"] == 1000.0
    assert first["positions"] == []

    second = data["snapshots"][1]

    assert second["cash"] == 900.0
    assert second["market_value"] == 340.0
    assert second["unrealized_pnl"] == 50.0
    assert second["gross_exposure"] == 340.0
    assert second["net_exposure"] == 100.0
    assert second["equity"] == 1240.0

    assert len(second["positions"]) == 2

    nq = second["positions"][0]

    assert nq["symbol"] == "NQ"
    assert nq["side"] == "long"
    assert nq["quantity"] == 2.0
    assert nq["average_price"] == 100.0
    assert nq["current_price"] == 110.0
    assert nq["cost_basis"] == 200.0
    assert nq["market_value"] == 220.0
    assert nq["unrealized_pnl"] == 20.0
    assert nq["return_percent"] == 10.0


def test_portfolio_json_exporter_creates_parent_directory(
    tmp_path,
):
    file_path = (
        tmp_path
        / "reports"
        / "portfolio.json"
    )

    PortfolioJsonExporter().export_json(
        report=build_report(),
        file_path=file_path,
    )

    assert file_path.exists()


def test_portfolio_json_exporter_uses_pretty_format(
    tmp_path,
):
    file_path = tmp_path / "portfolio.json"

    PortfolioJsonExporter().export_json(
        report=build_report(),
        file_path=file_path,
    )

    content = file_path.read_text(
        encoding="utf-8",
    )

    assert "\n" in content
    assert '  "summary"' in content
    assert '  "snapshots"' in content
