from __future__ import annotations

import json
from copy import deepcopy
from html import escape
from pathlib import Path

from backend.backtesting.strategy_validation_report_v2 import (
    StrategyValidationReportV2,
)


class StrategyValidationHtmlExporterV2:
    """
    Exporta un StrategyValidationReportV2
    a un archivo HTML.
    """

    def export(
        self,
        *,
        report,
        output_path,
    ) -> Path:

        if not isinstance(
            report,
            StrategyValidationReportV2,
        ):
            raise TypeError(
                "report debe ser "
                "StrategyValidationReportV2."
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

        summary_json = escape(
            json.dumps(
                payload["summary"],
                ensure_ascii=False,
                indent=2,
            )
        )

        walk_forward_json = escape(
            json.dumps(
                payload["walk_forward"],
                ensure_ascii=False,
                indent=2,
            )
        )

        monte_carlo_json = escape(
            json.dumps(
                payload["monte_carlo"],
                ensure_ascii=False,
                indent=2,
            )
        )

        html = (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8">\n'
            '  <meta name="viewport" '
            'content="width=device-width, initial-scale=1">\n'
            "  <title>Strategy Validation Report</title>\n"
            "  <style>\n"
            "    body {font-family:Arial,sans-serif;margin:40px;background:#f5f5f5;color:#111;}\n"
            "    main {max-width:1200px;margin:0 auto;background:#fff;padding:32px;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.08);}\n"
            "    h1,h2{margin-top:0;}\n"
            "    section{margin-top:28px;}\n"
            "    pre{overflow-x:auto;background:#111;color:#f5f5f5;padding:20px;border-radius:8px;}\n"
            "    .metric{font-size:1.25rem;font-weight:bold;padding:12px;background:#f0f0f0;border-radius:8px;}\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "<main>\n"
            "<h1>Strategy Validation Report</h1>\n"

            "<section>\n"
            "<h2>Summary</h2>\n"
            f"<pre>{summary_json}</pre>\n"
            "</section>\n"

            "<section>\n"
            "<h2>Validation Score</h2>\n"
            f'<div class="metric">{payload["summary"]["validation_score"]}</div>\n'
            "</section>\n"

            "<section>\n"
            "<h2>Backtest Score</h2>\n"
            f'<div class="metric">{payload["summary"]["backtest_score"]}</div>\n'
            "</section>\n"

            "<section>\n"
            "<h2>Walk Forward</h2>\n"
            f"<pre>{walk_forward_json}</pre>\n"
            "</section>\n"

            "<section>\n"
            "<h2>Monte Carlo</h2>\n"
            f"<pre>{monte_carlo_json}</pre>\n"
            "</section>\n"

            "</main>\n"
            "</body>\n"
            "</html>\n"
        )

        normalized_output_path.write_text(
            html,
            encoding="utf-8",
        )

        return normalized_output_path
