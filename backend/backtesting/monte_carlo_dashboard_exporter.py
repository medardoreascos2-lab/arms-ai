import html
import json
from pathlib import Path

from backend.backtesting.monte_carlo_report import (
    MonteCarloReport,
)


class MonteCarloDashboardExporter:
    """
    Genera un dashboard HTML estático para visualizar
    los resultados del análisis Monte Carlo.
    """

    def export_html(
        self,
        report: MonteCarloReport,
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
        report: MonteCarloReport,
    ) -> str:
        balance_labels = [
            "P5",
            "P50",
            "P95",
        ]

        balance_values = [
            report.final_balance_percentile_5,
            report.final_balance_percentile_50,
            report.final_balance_percentile_95,
        ]

        drawdown_labels = [
            "P50",
            "P95",
            "P99",
        ]

        drawdown_values = [
            report.drawdown_percentile_50,
            report.drawdown_percentile_95,
            report.drawdown_percentile_99,
        ]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Monte Carlo Dashboard</title>

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
                repeat(auto-fit, minmax(200px, 1fr));
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
            height: 340px;
        }}

        .percentile-grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px;
        }}

        .percentile-item {{
            background: var(--surface-light);
            border-radius: 10px;
            padding: 14px;
        }}

        .percentile-label {{
            color: var(--muted);
            font-size: 13px;
            margin-bottom: 6px;
        }}

        .percentile-value {{
            font-size: 20px;
            font-weight: 700;
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
            <h1>Monte Carlo Dashboard</h1>

            <div class="subtitle">
                ARMS AI simulation-based risk and
                robustness analysis
            </div>
        </header>

        <section class="grid">
            {self._metric_card(
                "Simulation Method",
                report.method,
            )}

            {self._metric_card(
                "Total Simulations",
                str(report.total_simulations),
            )}

            {self._metric_card(
                "Average Final Balance",
                f"${report.average_final_balance:.2f}",
                status="positive",
            )}

            {self._metric_card(
                "Median Final Balance",
                f"${report.median_final_balance:.2f}",
                status="positive",
            )}

            {self._metric_card(
                "Best Final Balance",
                f"${report.best_final_balance:.2f}",
                status="positive",
            )}

            {self._metric_card(
                "Worst Final Balance",
                f"${report.worst_final_balance:.2f}",
                status="negative",
            )}

            {self._metric_card(
                "Average Max Drawdown",
                f"${report.average_max_drawdown:.2f}",
                status="warning",
            )}

            {self._metric_card(
                "Worst Max Drawdown",
                f"${report.worst_max_drawdown:.2f}",
                status="negative",
            )}

            {self._metric_card(
                "Loss Probability",
                f"{report.loss_probability:.2f}%",
                status="warning",
            )}

            {self._metric_card(
                "Ruin Probability",
                f"{report.ruin_probability:.2f}%",
                status=(
                    "negative"
                    if report.ruin_probability > 0
                    else "positive"
                ),
            )}
        </section>

        <section class="card section">
            <h2>Final Balance Percentiles</h2>

            <div class="percentile-grid">
                {self._percentile_item(
                    "5th Percentile",
                    report.final_balance_percentile_5,
                )}

                {self._percentile_item(
                    "50th Percentile",
                    report.final_balance_percentile_50,
                )}

                {self._percentile_item(
                    "95th Percentile",
                    report.final_balance_percentile_95,
                )}
            </div>

            <div class="chart-wrapper">
                <canvas id="final-balance-chart"></canvas>
            </div>
        </section>

        <section class="card section">
            <h2>Drawdown Percentiles</h2>

            <div class="percentile-grid">
                {self._percentile_item(
                    "50th Percentile",
                    report.drawdown_percentile_50,
                )}

                {self._percentile_item(
                    "95th Percentile",
                    report.drawdown_percentile_95,
                )}

                {self._percentile_item(
                    "99th Percentile",
                    report.drawdown_percentile_99,
                )}
            </div>

            <div class="chart-wrapper">
                <canvas id="drawdown-chart"></canvas>
            </div>
        </section>

        <footer>
            Generated automatically by ARMS AI.
        </footer>
    </main>

    <script>
        const balanceLabels = {
            json.dumps(balance_labels)
        };

        const balanceValues = {
            json.dumps(balance_values)
        };

        const drawdownLabels = {
            json.dumps(drawdown_labels)
        };

        const drawdownValues = {
            json.dumps(drawdown_values)
        };

        const balanceContext = document
            .getElementById("final-balance-chart")
            .getContext("2d");

        new Chart(balanceContext, {{
            type: "bar",
            data: {{
                labels: balanceLabels,
                datasets: [
                    {{
                        label: "Final Balance",
                        data: balanceValues,
                        borderWidth: 1,
                    }},
                ],
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: false,
                        title: {{
                            display: true,
                            text: "Balance",
                        }},
                    }},
                }},
            }},
        }});

        const drawdownContext = document
            .getElementById("drawdown-chart")
            .getContext("2d");

        new Chart(drawdownContext, {{
            type: "bar",
            data: {{
                labels: drawdownLabels,
                datasets: [
                    {{
                        label: "Max Drawdown",
                        data: drawdownValues,
                        borderWidth: 1,
                    }},
                ],
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        title: {{
                            display: true,
                            text: "Drawdown",
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

    def _percentile_item(
        self,
        label: str,
        value: float,
    ) -> str:
        return f"""
        <article class="percentile-item">
            <div class="percentile-label">
                {html.escape(label)}
            </div>

            <div class="percentile-value">
                ${value:.2f}
            </div>
        </article>
        """
