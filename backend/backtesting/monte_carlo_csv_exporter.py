import csv
from pathlib import Path

from backend.backtesting.monte_carlo_report import (
    MonteCarloReport,
)


class MonteCarloCsvExporter:
    """
    Exporta un MonteCarloReport a un archivo CSV
    con columnas metric y value.
    """

    FIELDNAMES = [
        "metric",
        "value",
    ]

    def export_csv(
        self,
        report: MonteCarloReport,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        rows = self._build_rows(report)

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

            for metric, value in rows:
                writer.writerow(
                    {
                        "metric": metric,
                        "value": value,
                    }
                )

        return path

    def _build_rows(
        self,
        report: MonteCarloReport,
    ) -> list[tuple[str, str | int | float]]:
        return [
            (
                "method",
                report.method,
            ),
            (
                "total_simulations",
                report.total_simulations,
            ),
            (
                "average_final_balance",
                self._round_value(
                    report.average_final_balance
                ),
            ),
            (
                "median_final_balance",
                self._round_value(
                    report.median_final_balance
                ),
            ),
            (
                "best_final_balance",
                self._round_value(
                    report.best_final_balance
                ),
            ),
            (
                "worst_final_balance",
                self._round_value(
                    report.worst_final_balance
                ),
            ),
            (
                "average_max_drawdown",
                self._round_value(
                    report.average_max_drawdown
                ),
            ),
            (
                "worst_max_drawdown",
                self._round_value(
                    report.worst_max_drawdown
                ),
            ),
            (
                "loss_probability",
                self._round_value(
                    report.loss_probability
                ),
            ),
            (
                "ruin_probability",
                self._round_value(
                    report.ruin_probability
                ),
            ),
            (
                "final_balance_percentile_5",
                self._round_value(
                    report.final_balance_percentile_5
                ),
            ),
            (
                "final_balance_percentile_50",
                self._round_value(
                    report.final_balance_percentile_50
                ),
            ),
            (
                "final_balance_percentile_95",
                self._round_value(
                    report.final_balance_percentile_95
                ),
            ),
            (
                "drawdown_percentile_50",
                self._round_value(
                    report.drawdown_percentile_50
                ),
            ),
            (
                "drawdown_percentile_95",
                self._round_value(
                    report.drawdown_percentile_95
                ),
            ),
            (
                "drawdown_percentile_99",
                self._round_value(
                    report.drawdown_percentile_99
                ),
            ),
        ]

    def _round_value(
        self,
        value: float,
    ) -> float:
        return round(
            float(value),
            2,
        )
