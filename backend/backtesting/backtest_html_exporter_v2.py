from __future__ import annotations

import json
from html import escape
from pathlib import Path

from backend.backtesting.backtest_report_v2 import (
    BacktestReportV2,
)


class BacktestHtmlExporterV2:
    """
    Exporta un BacktestReportV2 a un archivo HTML.
    """

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

        summary_json = escape(
            json.dumps(
                payload["summary"],
                ensure_ascii=False,
                indent=2,
            )
        )

        full_report_json = escape(
            json.dumps(
                payload,
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
            "  <title>Backtest Report</title>\n"
            "  <style>\n"
            "    body {\n"
            "      font-family: Arial, sans-serif;\n"
            "      margin: 40px;\n"
            "      background: #f5f5f5;\n"
            "      color: #111;\n"
            "    }\n"
            "    main {\n"
            "      max-width: 1100px;\n"
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
            "    <h1>Backtest Report</h1>\n"
            "    <section>\n"
            "      <h2>Summary</h2>\n"
            f"      <pre>{summary_json}</pre>\n"
            "    </section>\n"
            "    <section>\n"
            "      <h2>Complete Report</h2>\n"
            f"      <pre>{full_report_json}</pre>\n"
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
