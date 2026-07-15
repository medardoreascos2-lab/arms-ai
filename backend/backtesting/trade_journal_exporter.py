import csv
from pathlib import Path
from typing import Any, Iterable


class TradeJournalExporter:
    """
    Exporta operaciones simuladas a un archivo CSV.
    """

    FIELDNAMES = [
        "opened_at",
        "closed_at",
        "symbol",
        "timeframe",
        "direction",
        "entry_price",
        "stop_loss",
        "take_profit",
        "exit_price",
        "result",
        "contracts",
        "point_value",
        "pnl",
        "duration_seconds",
    ]

    def export_csv(
        self,
        trades: Iterable[Any],
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=self.FIELDNAMES,
            )
            writer.writeheader()

            for trade in trades:
                writer.writerow(
                    self._serialize_trade(trade)
                )

        return path

    def _serialize_trade(
        self,
        trade: Any,
    ) -> dict[str, Any]:
        opened_at = getattr(
            trade,
            "opened_at",
            None,
        )
        closed_at = getattr(
            trade,
            "closed_at",
            None,
        )

        duration_seconds = None

        if (
            opened_at is not None
            and closed_at is not None
        ):
            duration_seconds = (
                closed_at - opened_at
            ).total_seconds()

        return {
            "opened_at": (
                opened_at.isoformat()
                if opened_at is not None
                else ""
            ),
            "closed_at": (
                closed_at.isoformat()
                if closed_at is not None
                else ""
            ),
            "symbol": getattr(
                trade,
                "symbol",
                "",
            ),
            "timeframe": getattr(
                trade,
                "timeframe",
                "",
            ),
            "direction": getattr(
                trade,
                "direction",
                "",
            ),
            "entry_price": getattr(
                trade,
                "entry_price",
                "",
            ),
            "stop_loss": getattr(
                trade,
                "stop_loss",
                "",
            ),
            "take_profit": getattr(
                trade,
                "take_profit",
                "",
            ),
            "exit_price": getattr(
                trade,
                "exit_price",
                "",
            ),
            "result": getattr(
                trade,
                "result",
                "",
            ),
            "contracts": getattr(
                trade,
                "contracts",
                "",
            ),
            "point_value": getattr(
                trade,
                "point_value",
                "",
            ),
            "pnl": getattr(
                trade,
                "pnl",
                "",
            ),
            "duration_seconds": (
                duration_seconds
                if duration_seconds is not None
                else ""
            ),
        }
