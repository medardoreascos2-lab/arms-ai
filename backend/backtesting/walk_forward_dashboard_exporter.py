import html
import json
from pathlib import Path

from backend.backtesting.walk_forward_report import (
    WalkForwardReport,
)


class WalkForwardDashboardExporter:
    """
    Genera un dashboard HTML estático para visualizar
    los resultados del análisis walk-forward.
    """

    def export_html(
        self,
        report: WalkForwardReport,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        document = self._build_html(report)

        path.write_text(
            document,
            encoding="utf-8",
        )

        return path

    def _build_html(
        self,
        report: WalkForwardReport,
    ) -> str:
        labels = [
            window.window_number
            for window in report.windows
        ]

        profits = [
            window.net_profit
            for window in report.windows
        ]

        rows = self._build_window_rows(
            report
        )

        best_window = self._format_optional_window(
            report.best_window_number,
            report.best_window_profit,
        )

        worst_window = self._format_optional_window(
            report.worst_window_number,
            report.worst_window_profit,
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>Walk Forward Dashboard</title>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        :root {{
            color-scheme: dark;
            --background: #07111f;
            --surface: #0f1b2d;
            --surface-light: #17263b;
            --border: #2b3d55;
            --text: #f8fafc;
            --muted: #94a3b8;
            --positive: #22c55e;
            --negative: #ef4444;
            --accent: #38bdf8;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--background);
            color: var(--text);
            font-family:
                Inter,
                system-ui,
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                sans-serif;
        }}

        .container {{
            width: min(1200px, calc(100% - 32px));
            margin: 0 auto;
            padding: 32px 0 64px;
        }}

        header {{
            margin-bottom: 28px;
        }}

        h1 {{
            margin: 0 0 8px;
            font-size: clamp(30px, 5vw, 46px);
        }}

        h2 {{
            margin-top: 0;
        }}

        .subtitle {{
            color: var(--muted);
            line-height: 1.6;
        }}

        .grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(190px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 18px;
            box-shadow:
                0 8px 24px rgba(0, 0, 0, 0.18);
        }}

        .metric-label {{
            color: var(--muted);
            font-size: 14px;
            margin-bottom: 8px;
        }}

        .metric-value {{
            font-size: 26px;
            font-weight: 700;
        }}

        .positive {{
            color: var(--positive);
        }}

        .negative {{
            color: var(--negative);
        }}

        .section {{
            margin-top: 24px;
        }}

        .chart-wrapper {{
            height: 360px;
        }}

        .table-wrapper {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 760px;
        }}

        th,
        td {{
            padding: 12px 10px;
            border-bottom: 1px solid var(--border);
            text-align: left;
            white-space: nowrap;
        }}

        th {{
            color: var(--muted);
            font-size: 13px;
        }}

        .empty-state {{
            color: var(--muted);
            padding: 20px 0;
        }}

        footer {{
            margin-top: 32px;
            color: var(--muted);
            font-size: 13px;
        }}
    </style>
</head>

<body>
    <main class="container">
        <header>
            <h1>Walk Forward Dashboard</h1>

            <div class="subtitle">
                ARMS AI quantitative validation report
            </div>
        </header>

        <section class="grid">
            {self._metric_card(
                "Total Windows",
                str(report.total_windows),
            )}

            {self._metric_card(
                "Profitable Windows",
                str(report.profitable_windows),
                positive=True,
            )}

            {self._metric_card(
                "Losing Windows",
                str(report.losing_windows),
                positive=False,
            )}

            {self._metric_card(
                "Breakeven Windows",
                str(report.breakeven_windows),
            )}

            {self._metric_card(
                "Total Net Profit",
                f"${report.total_net_profit:.2f}",
                positive=report.total_net_profit >= 0,
            )}

            {self._metric_card(
                "Average Net Profit",
                f"${report.average_net_profit:.2f}",
                positive=report.average_net_profit >= 0,
            )}

            {self._metric_card(
                "Profitable Window Rate",
                f"{report.profitable_window_rate:.2f}%",
            )}

            {self._metric_card(
                "Stability Score",
                f"{report.stability_score:.2f}",
            )}

            {self._metric_card(
                "Net Profit Std Dev",
                f"{report.net_profit_std_dev:.2f}",
            )}

            {self._metric_card(
                "Best Window",
                best_window,
                positive=True,
            )}

            {self._metric_card(
                "Worst Window",
                worst_window,
                positive=False,
            )}
        </section>

        <section class="card section">
            <h2>Net Profit by Window</h2>

            <div class="chart-wrapper">
                <canvas id="walk-forward-chart"></canvas>
            </div>
        </section>

        <section class="card section">
            <h2>Window Results</h2>

            {rows}
        </section>

        <footer>
            Generated automatically by ARMS AI.
        </footer>
    </main>

    <script>
        const labels = {json.dumps(labels)};
        const profits = {json.dumps(profits)};

        const context = document
            .getElementById("walk-forward-chart")
            .getContext("2d");

        new Chart(context, {{
            type: "bar",
            data: {{
                labels,
                datasets: [
                    {{
                        label: "Net Profit",
                        data: profits,
                        borderWidth: 1,
                    }},
                ],
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                interaction: {{
                    intersect: false,
                    mode: "index",
                }},
                scales: {{
                    x: {{
                        title: {{
                            display: true,
                            text: "Window",
                        }},
                    }},
                    y: {{
                        title: {{
                            display: true,
                            text: "Net Profit",
                        }},
                    }},
                }},
            }},
        }});
    </script>
</body>
</html>
"""

    def _metric_card(
        self,
        label: str,
        value: str,
        positive: bool | None = None,
    ) -> str:
        value_class = ""

        if positive is True:
            value_class = " positive"
        elif positive is False:
            value_class = " negative"

        return f"""
        <article class="card">
            <div class="metric-label">
                {html.escape(label)}
            </div>

            <div class="metric-value{value_class}">
                {html.escape(value)}
            </div>
        </article>
        """

    def _build_window_rows(
        self,
        report: WalkForwardReport,
    ) -> str:
        if not report.windows:
            return (
                '<div class="empty-state">'
                "No windows available"
                "</div>"
            )

        rows = []

        for window in report.windows:
            value_class = (
                "positive"
                if window.net_profit >= 0
                else "negative"
            )

            rows.append(
                f"""
                <tr>
                    <td>{window.window_number}</td>
                    <td>{window.training_start}</td>
                    <td>{window.training_end}</td>
                    <td>{window.testing_start}</td>
                    <td>{window.testing_end}</td>
                    <td class="{value_class}">
                        ${window.net_profit:.2f}
                    </td>
                </tr>
                """
            )

        return f"""
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>Window</th>
                        <th>Training Start</th>
                        <th>Training End</th>
                        <th>Testing Start</th>
                        <th>Testing End</th>
                        <th>Net Profit</th>
                    </tr>
                </thead>

                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _format_optional_window(
        self,
        window_number: int | None,
        profit: float | None,
    ) -> str:
        if window_number is None or profit is None:
            return "N/A"

        return (
            f"#{window_number} "
            f"(${profit:.2f})"
        )
