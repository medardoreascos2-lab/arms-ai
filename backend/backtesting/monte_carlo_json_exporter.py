import json
from pathlib import Path
from typing import Any

from backend.backtesting.monte_carlo_report import (
    MonteCarloReport,
)


class MonteCarloJsonExporter:
    """
    Exporta un MonteCarloReport a un archivo JSON.
    """

    def export_json(
        self,
        report: MonteCarloReport,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._build_payload(
            report=report,
        )

        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path

    def _build_payload(
        self,
        report: MonteCarloReport,
    ) -> dict[str, Any]:
        return {
            "total_simulations": report.total_simulations,
            "average_final_balance": self._round_value(
                report.average_final_balance
            ),
            "median_final_balance": self._round_value(
                report.median_final_balance
            ),
            "best_final_balance": self._round_value(
                report.best_final_balance
            ),
            "worst_final_balance": self._round_value(
                report.worst_final_balance
            ),
            "average_max_drawdown": self._round_value(
                report.average_max_drawdown
            ),
            "worst_max_drawdown": self._round_value(
                report.worst_max_drawdown
            ),
            "loss_probability": self._round_value(
                report.loss_probability
            ),
            "ruin_probability": self._round_value(
                report.ruin_probability
            ),
            "final_balance_percentiles": {
                "5": self._round_value(
                    report.final_balance_percentile_5
                ),
                "50": self._round_value(
                    report.final_balance_percentile_50
                ),
                "95": self._round_value(
                    report.final_balance_percentile_95
                ),
            },
            "drawdown_percentiles": {
                "50": self._round_value(
                    report.drawdown_percentile_50
                ),
                "95": self._round_value(
                    report.drawdown_percentile_95
                ),
                "99": self._round_value(
                    report.drawdown_percentile_99
                ),
            },
        }

    def _round_value(
        self,
        value: float,
    ) -> float:
        return round(
            float(value),
            2,
        )
