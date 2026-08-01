from __future__ import annotations

import json
from copy import deepcopy
from html import escape
from pathlib import Path

from backend.backtesting.walk_forward_report_v2 import (
    WalkForwardReportV2,
)


class WalkForwardHtmlExporterV2:
    """
    Exporta un WalkForwardReportV2 a un archivo HTML.
    """

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

        summary_json = escape(
            json.dumps(
                payload["summary"],
                ensure_ascii=False,
                indent=2,
            )
        )

        best_window_json = escape(
            json.dumps(
                payload["best_window"],
                ensure_ascii=False,
                indent=2,
            )
        )

        worst_window_json = escape(
            json.dumps(
                payload["worst_window"],
                ensure_ascii=False,
                indent=2,
            )
        )

        window_results_json = escape(
            json.dumps(
                payload["window_results"],
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
            "  <title>Walk Forward Report</title>\n"
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
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <main>\n"
            "    <h1>Walk Forward Report</h1>\n"
            "    <section>\n"
            "      <h2>Summary</h2>\n"
            f"      <pre>{summary_json}</pre>\n"
            "    </section>\n"
            "    <section>\n"
            "      <h2>Best Window</h2>\n"
            f"      <pre>{best_window_json}</pre>\n"
            "    </section>\n"
            "    <section>\n"
            "      <h2>Worst Window</h2>\n"
            f"      <pre>{worst_window_json}</pre>\n"
            "    </section>\n"
            "    <section>\n"
            "      <h2>Window Results</h2>\n"
            f"      <pre>{window_results_json}</pre>\n"
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
