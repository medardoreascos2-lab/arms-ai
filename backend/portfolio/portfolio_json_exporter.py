from __future__ import annotations

import json
from pathlib import Path

from backend.portfolio.portfolio_report import (
    PortfolioReport,
)


class PortfolioJsonExporter:
    """
    Exporta un PortfolioReport a JSON.
    """

    def export_json(
        self,
        *,
        report: PortfolioReport,
        file_path: str | Path,
    ) -> Path:
        file_path = Path(file_path)
        file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        file_path.write_text(
            json.dumps(
                self._build_data(report),
                indent=2,
            ),
            encoding="utf-8",
        )

        return file_path

    def _build_data(
        self,
        report: PortfolioReport,
    ) -> dict:
        return {
            "summary": {
                "total_snapshots": report.total_snapshots,
                "initial_equity": report.initial_equity,
                "final_equity": report.final_equity,
                "net_profit": report.net_profit,
                "return_percent": report.return_percent,
            },
            "risk": {
                "peak_equity": report.peak_equity,
                "max_drawdown": report.max_drawdown,
                "max_drawdown_percent": report.max_drawdown_percent,
            },
            "exposure": {
                "average_gross_exposure": report.average_gross_exposure,
                "max_gross_exposure": report.max_gross_exposure,
                "average_net_exposure": report.average_net_exposure,
                "max_net_exposure": report.max_net_exposure,
                "min_net_exposure": report.min_net_exposure,
            },
            "snapshots": [
                self._snapshot_data(snapshot)
                for snapshot in report.snapshots
            ],
        }

    def _snapshot_data(
        self,
        snapshot,
    ) -> dict:
        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "cash": snapshot.cash,
            "market_value": snapshot.market_value,
            "unrealized_pnl": snapshot.unrealized_pnl,
            "gross_exposure": snapshot.gross_exposure,
            "net_exposure": snapshot.net_exposure,
            "equity": snapshot.equity,
            "positions": [
                {
                    "symbol": position.symbol,
                    "side": position.side,
                    "quantity": position.quantity,
                    "average_price": position.average_price,
                    "current_price": position.current_price,
                    "cost_basis": position.cost_basis,
                    "market_value": position.market_value,
                    "unrealized_pnl": position.unrealized_pnl,
                    "return_percent": position.return_percent,
                }
                for position in snapshot.positions
            ],
        }
