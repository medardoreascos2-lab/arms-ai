from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from backend.backtesting.walk_forward_report_v2 import (
    WalkForwardReportV2,
)


class WalkForwardJsonExporterV2:
    """
    Exporta un WalkForwardReportV2 a un archivo JSON.
    """

    def __init__(
        self,
        *,
        indent: int = 4,
    ) -> None:

        if not isinstance(
            indent,
            int,
        ):
            raise TypeError(
                "indent debe ser int."
            )

        if indent < 0:
            raise ValueError(
                "indent no puede ser negativo."
            )

        self.indent = indent

    def export(
        self,
        *,
        report,
        output_path,
    ) -> Path:

        if not isinstance(
            report,
            WalkForwardReportV2,
        ):
            raise TypeError(
                "report debe ser WalkForwardReportV2."
            )

        normalized_output_path = Path(
            output_path
        )

        if (
            normalized_output_path.exists()
            and normalized_output_path.is_dir()
        ):
            raise ValueError(
                "output_path debe ser un archivo."
            )

        normalized_output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = deepcopy(
            report.to_dict()
        )

        normalized_output_path.write_text(
            json.dumps(
                payload,
                indent=self.indent,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        return normalized_output_path
