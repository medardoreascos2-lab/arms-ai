import csv
import json
from pathlib import Path

from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
)


class WalkForwardOptimizationCsvExporter:
    """
    Exporta las ventanas de optimización walk-forward
    y, opcionalmente, un resumen consolidado.
    """

    WINDOW_FIELDNAMES = [
        "window_number",
        "selected_parameters",
        "training_net_profit",
        "testing_net_profit",
        "performance_degradation",
        "degradation_rate",
        "overfit_suspected",
    ]

    SUMMARY_FIELDNAMES = [
        "metric",
        "value",
    ]

    def export_csv(
        self,
        report: WalkForwardOptimizationReport,
        file_path: str | Path,
        summary_path: str | Path | None = None,
    ) -> Path:
        windows_file_path = Path(file_path)

        windows_file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._write_windows(
            report=report,
            file_path=windows_file_path,
        )

        if summary_path is not None:
            summary_file_path = Path(summary_path)

            summary_file_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._write_summary(
                report=report,
                file_path=summary_file_path,
            )

        return windows_file_path

    def _write_windows(
        self,
        report: WalkForwardOptimizationReport,
        file_path: Path,
    ) -> None:
        with file_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=self.WINDOW_FIELDNAMES,
            )

            writer.writeheader()

            for window in report.windows:
                writer.writerow(
                    {
                        "window_number": (
                            window.window_number
                        ),
                        "selected_parameters": (
                            json.dumps(
                                window.selected_parameters,
                                ensure_ascii=False,
                                sort_keys=True,
                            )
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
                )

    def _write_summary(
        self,
        report: WalkForwardOptimizationReport,
        file_path: Path,
    ) -> None:
        rows = [
            (
                "total_windows",
                report.total_windows,
            ),
            (
                "profitable_testing_windows",
                report.profitable_testing_windows,
            ),
            (
                "losing_testing_windows",
                report.losing_testing_windows,
            ),
            (
                "breakeven_testing_windows",
                report.breakeven_testing_windows,
            ),
            (
                "total_training_net_profit",
                self._round_value(
                    report.total_training_net_profit
                ),
            ),
            (
                "total_testing_net_profit",
                self._round_value(
                    report.total_testing_net_profit
                ),
            ),
            (
                "average_training_net_profit",
                self._round_value(
                    report.average_training_net_profit
                ),
            ),
            (
                "average_testing_net_profit",
                self._round_value(
                    report.average_testing_net_profit
                ),
            ),
            (
                "average_performance_degradation",
                self._round_value(
                    report.average_performance_degradation
                ),
            ),
            (
                "testing_profitable_rate",
                self._round_value(
                    report.testing_profitable_rate
                ),
            ),
            (
                "overfit_windows",
                report.overfit_windows,
            ),
            (
                "overfit_rate",
                self._round_value(
                    report.overfit_rate
                ),
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

    def _round_value(
        self,
        value: float,
    ) -> float:
        return round(
            float(value),
            2,
        )
