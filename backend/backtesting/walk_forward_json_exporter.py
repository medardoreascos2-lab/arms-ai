import json
from pathlib import Path
from typing import Any

from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
)


class WalkForwardJsonExporter:
    """
    Exporta un WalkForwardReport a un archivo JSON.
    """

    def export_json(
        self,
        report: WalkForwardReport,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._build_payload(report)

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
        report: WalkForwardReport,
    ) -> dict[str, Any]:
        return {
            "summary": {
                "total_windows": report.total_windows,
                "profitable_windows": (
                    report.profitable_windows
                ),
                "losing_windows": report.losing_windows,
                "breakeven_windows": (
                    report.breakeven_windows
                ),
                "total_net_profit": self._round_value(
                    report.total_net_profit
                ),
                "average_net_profit": self._round_value(
                    report.average_net_profit
                ),
                "profitable_window_rate": (
                    self._round_value(
                        report.profitable_window_rate
                    )
                ),
                "net_profit_std_dev": self._round_value(
                    report.net_profit_std_dev
                ),
                "stability_score": self._round_value(
                    report.stability_score
                ),
                "best_window_number": (
                    report.best_window_number
                ),
                "best_window_profit": (
                    self._round_optional(
                        report.best_window_profit
                    )
                ),
                "worst_window_number": (
                    report.worst_window_number
                ),
                "worst_window_profit": (
                    self._round_optional(
                        report.worst_window_profit
                    )
                ),
            },
            "windows": [
                {
                    "window_number": window.window_number,
                    "training_start": (
                        window.training_start
                    ),
                    "training_end": window.training_end,
                    "testing_start": window.testing_start,
                    "testing_end": window.testing_end,
                    "net_profit": self._round_value(
                        window.net_profit
                    ),
                }
                for window in report.windows
            ],
        }

    def _round_value(
        self,
        value: float,
    ) -> float:
        return round(
            float(value),
            2,
        )

    def _round_optional(
        self,
        value: float | None,
    ) -> float | None:
        if value is None:
            return None

        return self._round_value(value)
