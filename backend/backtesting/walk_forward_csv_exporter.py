import csv
from pathlib import Path

from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
)


class WalkForwardCsvExporter:
    """
    Exporta las ventanas walk-forward y, opcionalmente,
    un resumen consolidado en archivos CSV separados.
    """

    WINDOW_FIELDNAMES = [
        "window_number",
        "training_start",
        "training_end",
        "testing_start",
        "testing_end",
        "net_profit",
    ]

    SUMMARY_FIELDNAMES = [
        "metric",
        "value",
    ]

    def export_csv(
        self,
        report: WalkForwardReport,
        file_path: str | Path,
        summary_path: str | Path | None = None,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._write_windows(
            report=report,
            file_path=path,
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

        return path

    def _write_windows(
        self,
        report: WalkForwardReport,
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
                        "training_start": (
                            window.training_start
                        ),
                        "training_end": (
                            window.training_end
                        ),
                        "testing_start": (
                            window.testing_start
                        ),
                        "testing_end": (
                            window.testing_end
                        ),
                        "net_profit": self._round_value(
                            window.net_profit
                        ),
                    }
                )

    def _write_summary(
        self,
        report: WalkForwardReport,
        file_path: Path,
    ) -> None:
        rows = [
            (
                "total_windows",
                report.total_windows,
            ),
            (
                "profitable_windows",
                report.profitable_windows,
            ),
            (
                "losing_windows",
                report.losing_windows,
            ),
            (
                "breakeven_windows",
                report.breakeven_windows,
            ),
            (
                "total_net_profit",
                self._round_value(
                    report.total_net_profit
                ),
            ),
            (
                "average_net_profit",
                self._round_value(
                    report.average_net_profit
                ),
            ),
            (
                "profitable_window_rate",
                self._round_value(
                    report.profitable_window_rate
                ),
            ),
            (
                "net_profit_std_dev",
                self._round_value(
                    report.net_profit_std_dev
                ),
            ),
            (
                "stability_score",
                self._round_value(
                    report.stability_score
                ),
            ),
            (
                "best_window_number",
                self._serialize_optional(
                    report.best_window_number
                ),
            ),
            (
                "best_window_profit",
                self._serialize_optional_number(
                    report.best_window_profit
                ),
            ),
            (
                "worst_window_number",
                self._serialize_optional(
                    report.worst_window_number
                ),
            ),
            (
                "worst_window_profit",
                self._serialize_optional_number(
                    report.worst_window_profit
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

    def _serialize_optional(
        self,
        value: int | None,
    ) -> int | str:
        if value is None:
            return ""

        return value

    def _serialize_optional_number(
        self,
        value: float | None,
    ) -> float | str:
        if value is None:
            return ""

        return self._round_value(value)
