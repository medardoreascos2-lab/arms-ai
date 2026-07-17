from __future__ import annotations

import csv
from pathlib import Path

from backend.portfolio.portfolio_report import (
    PortfolioReport,
)


class PortfolioCsvExporter:
    """
    Exporta un PortfolioReport a dos archivos CSV:
    resumen general y evolución por snapshot.
    """

    SUMMARY_FIELDNAMES = [
        "metric",
        "value",
    ]

    SNAPSHOT_FIELDNAMES = [
        "timestamp",
        "cash",
        "market_value",
        "unrealized_pnl",
        "gross_exposure",
        "net_exposure",
        "equity",
        "total_positions",
    ]

    def export_csv(
        self,
        *,
        report: PortfolioReport,
        summary_file: str | Path,
        snapshots_file: str | Path,
    ) -> tuple[Path, Path]:
        summary_path = Path(summary_file)
        snapshots_path = Path(snapshots_file)

        summary_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        snapshots_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._write_summary(
            report=report,
            file_path=summary_path,
        )
        self._write_snapshots(
            report=report,
            file_path=snapshots_path,
        )

        return (
            summary_path,
            snapshots_path,
        )

    def _write_summary(
        self,
        *,
        report: PortfolioReport,
        file_path: Path,
    ) -> None:
        rows = [
            (
                "total_snapshots",
                report.total_snapshots,
            ),
            (
                "initial_equity",
                report.initial_equity,
            ),
            (
                "final_equity",
                report.final_equity,
            ),
            (
                "net_profit",
                report.net_profit,
            ),
            (
                "return_percent",
                report.return_percent,
            ),
            (
                "peak_equity",
                report.peak_equity,
            ),
            (
                "max_drawdown",
                report.max_drawdown,
            ),
            (
                "max_drawdown_percent",
                report.max_drawdown_percent,
            ),
            (
                "average_gross_exposure",
                report.average_gross_exposure,
            ),
            (
                "max_gross_exposure",
                report.max_gross_exposure,
            ),
            (
                "average_net_exposure",
                report.average_net_exposure,
            ),
            (
                "max_net_exposure",
                report.max_net_exposure,
            ),
            (
                "min_net_exposure",
                report.min_net_exposure,
            ),
        ]

        with file_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=self.SUMMARY_FIELDNAMES,
            )

            writer.writeheader()

            for metric, value in rows:
                writer.writerow(
                    {
                        "metric": metric,
                        "value": value,
                    }
                )

    def _write_snapshots(
        self,
        *,
        report: PortfolioReport,
        file_path: Path,
    ) -> None:
        with file_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=self.SNAPSHOT_FIELDNAMES,
            )

            writer.writeheader()

            for snapshot in report.snapshots:
                writer.writerow(
                    {
                        "timestamp": (
                            snapshot.timestamp.isoformat()
                        ),
                        "cash": snapshot.cash,
                        "market_value": (
                            snapshot.market_value
                        ),
                        "unrealized_pnl": (
                            snapshot.unrealized_pnl
                        ),
                        "gross_exposure": (
                            snapshot.gross_exposure
                        ),
                        "net_exposure": (
                            snapshot.net_exposure
                        ),
                        "equity": snapshot.equity,
                        "total_positions": (
                            snapshot.total_positions
                        ),
                    }
                )
