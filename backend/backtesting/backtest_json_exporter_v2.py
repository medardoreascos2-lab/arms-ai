from __future__ import annotations

import json
from pathlib import Path

from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


class BacktestJsonExporterV2:
    """
    Exporta un BacktestReportV2 a un archivo JSON.
    """

    def __init__(
        self,
        *,
        indent: int = 2,
    ) -> None:

        if not isinstance(
            indent,
            int,
        ):
            raise TypeError(
                "indent debe ser un int."
            )

        if indent < 0:
            raise ValueError(
                "indent no puede ser negativo."
            )

        self.indent = indent

    def export(
        self,
        *,
        report: BacktestReportV2,
        output_path,
    ) -> Path:

        if not isinstance(
            report,
            BacktestReportV2,
        ):
            raise TypeError(
                "report debe ser BacktestReportV2."
            )

        normalized_output_path = Path(
            output_path
        )

        if (
            normalized_output_path.exists()
            and normalized_output_path.is_dir()
        ):
            raise ValueError(
                "output_path no puede ser un directorio."
            )

        normalized_output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = report.to_dict()

        normalized_output_path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=self.indent,
            )
            + "\n",
            encoding="utf-8",
        )

        return normalized_output_path
