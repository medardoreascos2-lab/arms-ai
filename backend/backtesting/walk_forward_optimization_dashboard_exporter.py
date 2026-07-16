import html
import json
from pathlib import Path

from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
)


class WalkForwardOptimizationDashboardExporter:
    """
    Genera un dashboard HTML estático para visualizar
    los resultados de una optimización walk-forward.
    """

    def export_html(
        self,
        report: WalkForwardOptimizationReport,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            self._build_html(report),
            encoding="utf-8",
        )

        return path

    def _build_html(
        self,
        report: WalkForwardOptimizationReport,
    ) -> str:
        window_labels = [
            window.window_number
            for window in report.windows
        ]

        training_values = [
            window.training_net_profit
            for window in report.windows
        ]

        testing_values = [
            window.testing_net_profit
            for window in report.windows
        ]

        degradation_values = [
            window.degradation_rate
            for window in report.windows
        ]

        table_content = self._build_window_table(
            report
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>
        ARMS AI Walk Forward Optimization Dashboard
    </title>

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
            --warning: #f59e0b;
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
            width: min(1280px, calc(100% - 32px));
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

        .warning {{
            color: var(--warning);
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
            min-width: 1050px;
        }}

        th,
        td {{
            padding: 12px 10px;
            border-bottom: 1px solid var(--border);
            text-align: left;
            vertical-align: top;
            white-space: nowrap;
        }}

        th {{
            color: var(--muted);
            font-size: 13px;
        }}

        code {{
            display: inline-block;
            background: var(--surface-light);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 5px 8px;
            color: var(--accent);
            white-space: normal;
        }}

        .badge {{
            display: inline-block;
            padding: 5px 9px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
        }}

        .badge-safe {{
            background: rgba(34, 197, 94, 0.14);
            color: var(--positive);
        }}

        .badge-overfit {{
            background: rgba(239, 68, 68, 0.14);
            color: var(--negative);
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
            <h1>
                Walk Forward Optimization Dashboard
            </h1>

            <div class="subtitle">
                ARMS AI training versus out-of-sample
                optimization analysis
            </div>
        </header>

        <section class="grid">
            {self._metric_card(
                label="Total Windows",
                value=str(report.total_windows),
            )}

            {self._metric_card(
                label="Profitable Testing Windows",
                value=str(
                    report.profitable_testing_windows
                ),
                status="positive",
            )}

            {self._metric_card(
                label="Losing Testing Windows",
                value=str(
                    report.losing_testing_windows
                ),
                status="negative",
            )}

            {self._metric_card(
                label="Testing Net Profit",
                value=(
                    f"${report.total_testing_net_profit:.2f}"
                ),
                status=(
                    "positive"
                    if report.total_testing_net_profit >= 0
                    else "negative"
                ),
            )}

            {self._metric_card(
                label="Training Net Profit",
                value=(
                    f"${report.total_training_net_profit:.2f}"
                ),
                status=(
                    "positive"
                    if report.total_training_net_profit >= 0
                    else "negative"
                ),
            )}

            {self._metric_card(
                label="Average Testing Profit",
                value=(
                    f"${report.average_testing_net_profit:.2f}"
                ),
                status=(
                    "positive"
                    if report.average_testing_net_profit >= 0
                    else "negative"
                ),
            )}

            {self._metric_card(
                label="Testing Profitable Rate",
                value=(
                    f"{report.testing_profitable_rate:.2f}%"
                ),
            )}

            {self._metric_card(
                label="Average Degradation",
                value=(
                    f"${report.average_performance_degradation:.2f}"
                ),
                status="warning",
            )}

            {self._metric_card(
                label="Overfit Windows",
                value=str(report.overfit_windows),
                status=(
                    "negative"
                    if report.overfit_windows > 0
                    else "positive"
                ),
            )}

            {self._metric_card(
                label="Overfit Rate",
                value=f"{report.overfit_rate:.2f}%",
                status=(
                    "negative"
                    if report.overfit_rate > 0
                    else "positive"
                ),
            )}
        </section>

        <section class="card section">
            <h2>
                Training vs Testing Net Profit
            </h2>

            <div class="chart-wrapper">
                <canvas id="profit-chart"></canvas>
            </div>
        </section>

        <section class="card section">
            <h2>
                Performance Degradation
            </h2>

            <div class="chart-wrapper">
                <canvas id="degradation-chart"></canvas>
            </div>
        </section>

        <section class="card section">
            <h2>
                Optimization Window Results
            </h2>

            {table_content}
        </section>

        <footer>
            Generated automatically by ARMS AI.
        </footer>
    </main>

    <script>
        const labels = {json.dumps(window_labels)};
        const trainingValues = {
            json.dumps(training_values)
        };
        const testingValues = {
            json.dumps(testing_values)
        };
        const degradationValues = {
            json.dumps(degradation_values)
        };

        const profitContext = document
            .getElementById("profit-chart")
            .getContext("2d");

        new Chart(profitContext, {{
            type: "bar",
            data: {{
                labels,
                datasets: [
                    {{
                        label: "Training",
                        data: trainingValues,
                        borderWidth: 1,
                    }},
                    {{
                        label: "Testing",
                        data: testingValues,
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

        const degradationContext = document
            .getElementById("degradation-chart")
            .getContext("2d");

        new Chart(degradationContext, {{
            type: "line",
            data: {{
                labels,
                datasets: [
                    {{
                        label: "Degradation Rate (%)",
                        data: degradationValues,
                        borderWidth: 2,
                        tension: 0.2,
                        fill: false,
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
                            text: "Degradation Rate (%)",
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
        status: str | None = None,
    ) -> str:
        value_class = "metric-value"

        if status:
            value_class += f" {status}"

        return f"""
        <article class="card">
            <div class="metric-label">
                {html.escape(label)}
            </div>

            <div class="{value_class}">
                {html.escape(value)}
            </div>
        </article>
        """

    def _build_window_table(
        self,
        report: WalkForwardOptimizationReport,
    ) -> str:
        if not report.windows:
            return (
                '<div class="empty-state">'
                "No optimization windows available."
                "</div>"
            )

        rows = []

        for window in report.windows:
            parameters = json.dumps(
                window.selected_parameters,
                ensure_ascii=False,
                sort_keys=True,
            )

            testing_class = (
                "positive"
                if window.testing_net_profit >= 0
                else "negative"
            )

            if window.overfit_suspected:
                overfit_badge = (
                    '<span class="badge badge-overfit">'
                    "Suspected"
                    "</span>"
                )
            else:
                overfit_badge = (
                    '<span class="badge badge-safe">'
                    "No"
                    "</span>"
                )

            rows.append(
                f"""
                <tr>
                    <td>{window.window_number}</td>

                    <td>
                        <code>
                            {html.escape(parameters)}
                        </code>
                    </td>

                    <td>
                        ${window.training_net_profit:.2f}
                    </td>

                    <td class="{testing_class}">
                        ${window.testing_net_profit:.2f}
                    </td>

                    <td>
                        ${window.performance_degradation:.2f}
                    </td>

                    <td>
                        {window.degradation_rate:.2f}%
                    </td>

                    <td>
                        {overfit_badge}
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
                        <th>Selected Parameters</th>
                        <th>Training</th>
                        <th>Testing</th>
                        <th>Degradation</th>
                        <th>Degradation Rate</th>
                        <th>Overfit</th>
                    </tr>
                </thead>

                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """
