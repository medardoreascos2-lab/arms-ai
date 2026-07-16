import json
from pathlib import Path
from typing import Any

from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
)


class WalkForwardOptimizationJsonExporter:
    """
    Exporta un WalkForwardOptimizationReport a JSON.
    """

    def export_json(
        self,
        report: WalkForwardOptimizationReport,
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
        report: WalkForwardOptimizationReport,
    ) -> dict[str, Any]:
        return {
            "summary": {
                "total_windows": report.total_windows,
                "profitable_testing_windows": (
                    report.profitable_testing_windows
                ),
                "losing_testing_windows": (
                    report.losing_testing_windows
                ),
                "breakeven_testing_windows": (
                    report.breakeven_testing_windows
                ),
                "total_training_net_profit": (
                    self._round_value(
                        report.total_training_net_profit
                    )
                ),
                "total_testing_net_profit": (
                    self._round_value(
                        report.total_testing_net_profit
                    )
                ),
                "average_training_net_profit": (
                    self._round_value(
                        report.average_training_net_profit
                    )
                ),
                "average_testing_net_profit": (
                    self._round_value(
                        report.average_testing_net_profit
                    )
                ),
                "average_performance_degradation": (
                    self._round_value(
                        report.average_performance_degradation
                    )
                ),
                "testing_profitable_rate": (
                    self._round_value(
                        report.testing_profitable_rate
                    )
                ),
                "overfit_windows": report.overfit_windows,
                "overfit_rate": self._round_value(
                    report.overfit_rate
                ),
            },
            "windows": [
                {
                    "window_number": window.window_number,
                    "selected_parameters": dict(
                        window.selected_parameters
                    ),
                    "training_net_profit": (
                        self._round_value(
                            window.training_net_profit
                        )
                    ),
                    "testing_net_profit": (
                        self._round_value(
                            window.testing_net_profit
                        )
                    ),
                    "performance_degradation": (
                        self._round_value(
                            window.performance_degradation
                        )
                    ),
                    "degradation_rate": (
                        self._round_value(
                            window.degradation_rate
                        )
                    ),
                    "overfit_suspected": (
                        window.overfit_suspected
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
