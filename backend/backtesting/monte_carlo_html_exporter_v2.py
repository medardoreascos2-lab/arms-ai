from __future__ import annotations

import json
from copy import deepcopy
from html import escape
from pathlib import Path

from backend.backtesting.monte_carlo_report_v2 import (
    MonteCarloReportV2,
)


class MonteCarloHtmlExporterV2:
    """
    Exporta un MonteCarloReportV2 a un archivo HTML.
    """

    def export(
        self,
        *,
        report,
        output_path,
    ) -> Path:

        if not isinstance(
            report,
            MonteCarloReportV2,
        ):
            raise TypeError(
                "report debe ser MonteCarloReportV2."
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

        best_final_equity = escape(
            str(
                payload["best_final_equity"]
            )
        )

        worst_final_equity = escape(
            str(
                payload["worst_final_equity"]
            )
        )

        maximum_drawdowns_json = escape(
            json.dumps(
                payload["maximum_drawdowns"],
                ensure_ascii=False,
                indent=2,
            )
        )

        equity_curves_json = escape(
            json.dumps(
                payload["equity_curves"],
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
            "  <title>Monte Carlo Report</title>\n"
            "  <style>\n"
            "    body {\n"
            "      font-family: Arial, sans-serif;\n"
            "      margin: 40px;\n"
            "      background: #f5f5f5;\n"
            "      color: #111;\n"
            "    }\n"
            "    main {\n"
            "      max-width: 1200px;\n"
            "      margin: 0 auto;\n"
            "      background: #fff;\n"
            "      padding: 32px;\n"
            "      border-radius: 12px;\n"
            "      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);\n"
            "    }\n"
            "    h1, h2 {\n"
            "      margin-top: 0;\n"
            "    }\n"
            "    section {\n"
            "      margin-top: 28px;\n"
            "    }\n"
            "    pre {\n"
            "      overflow-x: auto;\n"
            "      background: #111;\n"
            "      color: #f5f5f5;\n"
            "      padding: 20px;\n"
            "      border-radius: 8px;\n"
            "      line-height: 1.45;\n"
            "    }\n"
            "    .metric {\n"
            "      font-size: 1.35rem;\n"
            "      font-weight: bold;\n"
            "      padding: 14px;\n"
            "      background: #f0f0f0;\n"
            "      border-radius: 8px;\n"
            "    }\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <main>\n"
            "    <h1>Monte Carlo Report</h1>\n"
            "    <section>\n"
            "      <h2>Summary</h2>\n"
            f"      <pre>{summary_json}</pre>\n"
            "    </section>\n"
            "    <section>\n"
            "      <h2>Best Final Equity</h2>\n"
            f'      <div class="metric">{best_final_equity}</div>\n'
            "    </section>\n"
            "    <section>\n"
            "      <h2>Worst Final Equity</h2>\n"
            f'      <div class="metric">{worst_final_equity}</div>\n'
            "    </section>\n"
            "    <section>\n"
            "      <h2>Maximum Drawdowns</h2>\n"
            f"      <pre>{maximum_drawdowns_json}</pre>\n"
            "    </section>\n"
            "    <section>\n"
            "      <h2>Equity Curves</h2>\n"
            f"      <pre>{equity_curves_json}</pre>\n"
            "    </section>\n"
            "  </main>\n"
            "</body>\n"
            "</html>\n"
        )

        normalized_output_path.write_text(
            html,
            encoding="utf-8",
        )

        return normalized_output_path
