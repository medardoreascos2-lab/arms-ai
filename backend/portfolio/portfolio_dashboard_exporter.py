from __future__ import annotations

import html
import json
from pathlib import Path

from backend.portfolio.portfolio_report import (
    PortfolioReport,
)


class PortfolioDashboardExporter:
    """
    Genera un dashboard HTML estático para un PortfolioReport.
    """

    def export_dashboard(
        self,
        *,
        report: PortfolioReport,
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
        report: PortfolioReport,
    ) -> str:
        timestamps = [
            snapshot.timestamp.isoformat()
            for snapshot in report.snapshots
        ]

        equity_values = [
            snapshot.equity
            for snapshot in report.snapshots
        ]

        gross_exposure_values = [
            snapshot.gross_exposure
            for snapshot in report.snapshots
        ]

        net_exposure_values = [
            snapshot.net_exposure
            for snapshot in report.snapshots
        ]

        snapshot_rows = "".join(
            self._snapshot_row(snapshot)
            for snapshot in report.snapshots
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Portfolio Dashboard</title>

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
            width: min(1240px, calc(100% - 32px));
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
                repeat(auto-fit, minmax(210px, 1fr));
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

        .table-wrapper {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            padding: 12px 14px;
            text-align: right;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}

        th:first-child,
        td:first-child {{
            text-align: left;
        }}

        th {{
            color: var(--muted);
            font-size: 13px;
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
            <h1>Portfolio Dashboard</h1>

            <div class="subtitle">
                ARMS AI portfolio performance,
                risk and exposure analysis
            </div>
        </header>

        <section class="grid">
            {self._metric_card(
                "Initial Equity",
                f"${report.initial_equity:.2f}",
            )}

            {self._metric_card(
                "Final Equity",
                f"${report.final_equity:.2f}",
                status=(
                    "positive"
                    if report.final_equity >= report.initial_equity
                    else "negative"
                ),
            )}

            {self._metric_card(
                "Net Profit",
                f"${report.net_profit:.2f}",
                status=(
                    "positive"
                    if report.net_profit >= 0
                    else "negative"
                ),
            )}

            {self._metric_card(
                "Return %",
                f"{report.return_percent:.2f}%",
                status=(
                    "positive"
                    if report.return_percent >= 0
                    else "negative"
                ),
            )}

            {self._metric_card(
                "Peak Equity",
                f"${report.peak_equity:.2f}",
            )}

            {self._metric_card(
                "Max Drawdown",
                f"${report.max_drawdown:.2f}",
                status="negative",
            )}

            {self._metric_card(
                "Max Drawdown %",
                f"{report.max_drawdown_percent:.2f}%",
                status="warning",
            )}

            {self._metric_card(
                "Average Gross Exposure",
                f"${report.average_gross_exposure:.2f}",
            )}

            {self._metric_card(
                "Max Gross Exposure",
                f"${report.max_gross_exposure:.2f}",
            )}

            {self._metric_card(
                "Average Net Exposure",
                f"${report.average_net_exposure:.2f}",
            )}

            {self._metric_card(
                "Snapshots",
                str(report.total_snapshots),
            )}
        </section>

        <section class="card section">
            <h2>Equity Curve</h2>

            <div class="chart-wrapper">
                <canvas id="equity-chart"></canvas>
            </div>
        </section>

        <section class="card section">
            <h2>Exposure</h2>

            <div class="chart-wrapper">
                <canvas id="exposure-chart"></canvas>
            </div>
        </section>

        <section class="card section">
            <h2>Snapshots</h2>

            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Cash</th>
                            <th>Market Value</th>
                            <th>Unrealized P&amp;L</th>
                            <th>Gross Exposure</th>
                            <th>Net Exposure</th>
                            <th>Equity</th>
                            <th>Positions</th>
                        </tr>
                    </thead>

                    <tbody>
                        {snapshot_rows}
                    </tbody>
                </table>
            </div>
        </section>

        <footer>
            Generated automatically by ARMS AI.
        </footer>
    </main>

    <script>
        const labels = {json.dumps(timestamps)};

        const equityValues = {
            json.dumps(equity_values)
        };

        const grossExposureValues = {
            json.dumps(gross_exposure_values)
        };

        const netExposureValues = {
            json.dumps(net_exposure_values)
        };

        new Chart(
            document
                .getElementById("equity-chart")
                .getContext("2d"),
            {{
                type: "line",
                data: {{
                    labels,
                    datasets: [
                        {{
                            label: "Equity",
                            data: equityValues,
                            borderWidth: 2,
                            tension: 0.2,
                        }},
                    ],
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                }},
            }},
        );

        new Chart(
            document
                .getElementById("exposure-chart")
                .getContext("2d"),
            {{
                type: "line",
                data: {{
                    labels,
                    datasets: [
                        {{
                            label: "Gross Exposure",
                            data: grossExposureValues,
                            borderWidth: 2,
                            tension: 0.2,
                        }},
                        {{
                            label: "Net Exposure",
                            data: netExposureValues,
                            borderWidth: 2,
                            tension: 0.2,
                        }},
                    ],
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                }},
            }},
        );
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

    def _snapshot_row(
        self,
        snapshot,
    ) -> str:
        return f"""
        <tr>
            <td>{html.escape(snapshot.timestamp.isoformat())}</td>
            <td>{snapshot.cash}</td>
            <td>{snapshot.market_value}</td>
            <td>{snapshot.unrealized_pnl}</td>
            <td>{snapshot.gross_exposure}</td>
            <td>{snapshot.net_exposure}</td>
            <td>{snapshot.equity}</td>
            <td>{snapshot.total_positions}</td>
        </tr>
        """
