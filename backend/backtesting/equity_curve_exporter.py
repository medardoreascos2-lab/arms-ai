import csv
from pathlib import Path

from backend.backtesting.equity_curve import EquityCurve


class EquityCurveExporter:
    """
    Exporta una curva de equity a un archivo CSV.
    """

    FIELDNAMES = [
        "trade_number",
        "pnl",
        "balance",
        "peak_balance",
        "drawdown",
    ]

    def export_csv(
        self,
        equity_curve: EquityCurve,
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

            writer.writerow(
                {
                    "trade_number": 0,
                    "pnl": 0.0,
                    "balance": round(
                        equity_curve.initial_balance,
                        2,
                    ),
                    "peak_balance": round(
                        equity_curve.initial_balance,
                        2,
                    ),
                    "drawdown": 0.0,
                }
            )

            for point in equity_curve.points:
                writer.writerow(
                    {
                        "trade_number": point.trade_number,
                        "pnl": round(point.pnl, 2),
                        "balance": round(point.balance, 2),
                        "peak_balance": round(
                            point.peak_balance,
                            2,
                        ),
                        "drawdown": round(
                            point.drawdown,
                            2,
                        ),
                    }
                )

        return path
