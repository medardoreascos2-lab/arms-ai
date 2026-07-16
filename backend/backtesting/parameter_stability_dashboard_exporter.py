import html
import json
from pathlib import Path

from backend.backtesting.parameter_stability_analyzer import (
    ParameterStabilityAnalysis,
)


class ParameterStabilityDashboardExporter:
    """
    Genera un dashboard HTML estático con la estabilidad
    de los parámetros seleccionados entre ventanas.
    """

    def export_html(
        self,
        analysis: ParameterStabilityAnalysis,
        file_path: str | Path,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            self._build_html(analysis),
            encoding="utf-8",
        )

        return path

    def _build_html(
        self,
        analysis: ParameterStabilityAnalysis,
    ) -> str:
        parameter_names = list(
            analysis.parameters.keys()
        )

        stability_scores = [
            analysis.parameters[name].stability_score
            for name in parameter_names
        ]

        frequency_data = {
            name: {
                str(value): count
                for value, count in (
                    summary.frequencies.items()
                )
            }
            for name, summary in (
                analysis.parameters.items()
            )
        }

        cards = self._build_parameter_cards(
            analysis
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Parameter Stability Dashboard</title>

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
            --warning: #f59e0b;
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

        h2,
        h3 {{
            margin-top: 0;
        }}

        .subtitle {{
            color: var(--muted);
            line-height: 1.6;
        }}

        .summary-grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .parameter-grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
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
            font-size: 28px;
            font-weight: 700;
        }}

        .section {{
            margin-top: 24px;
        }}

        .chart-wrapper {{
            height: 360px;
        }}

        .details {{
            display: grid;
            gap: 10px;
        }}

        .detail-row {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border);
        }}

        .detail-label {{
            color: var(--muted);
        }}

        .frequency-list {{
            margin: 14px 0 0;
            padding: 0;
            list-style: none;
        }}

        .frequency-item {{
            display: flex;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 8px;
            padding: 10px 12px;
            background: var(--surface-light);
            border-radius: 8px;
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
            <h1>Parameter Stability Dashboard</h1>

            <div class="subtitle">
                ARMS AI parameter consistency analysis
            </div>
        </header>

        <section class="summary-grid">
            {self._metric_card(
                label="Overall Stability",
                value=(
                    f"{analysis.overall_stability_score:.2f}"
                ),
            )}

            {self._metric_card(
                label="Total Windows",
                value=str(analysis.total_windows),
            )}

            {self._metric_card(
                label="Parameters Analyzed",
                value=str(len(analysis.parameters)),
            )}
        </section>

        <section class="card section">
            <h2>Stability Score by Parameter</h2>

            <div class="chart-wrapper">
                <canvas id="stability-chart"></canvas>
            </div>
        </section>

        <section class="section">
            {cards}
        </section>

        <footer>
            Generated automatically by ARMS AI.
        </footer>
    </main>

    <script>
        const labels = {json.dumps(parameter_names)};
        const stabilityScores = {
            json.dumps(stability_scores)
        };

        const frequencyData = {
            json.dumps(
                frequency_data,
                ensure_ascii=False,
                sort_keys=True,
            )
        };

        const context = document
            .getElementById("stability-chart")
            .getContext("2d");

        new Chart(context, {{
            type: "bar",
            data: {{
                labels,
                datasets: [
                    {{
                        label: "Stability Score",
                        data: stabilityScores,
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
                        max: 100,
                        title: {{
                            display: true,
                            text: "Score",
                        }},
                    }},
                    x: {{
                        title: {{
                            display: true,
                            text: "Parameter",
                        }},
                    }},
                }},
            }},
        }});

        window.parameterFrequencyData = frequencyData;
    </script>
</body>
</html>
"""

    def _metric_card(
        self,
        label: str,
        value: str,
    ) -> str:
        return f"""
        <article class="card">
            <div class="metric-label">
                {html.escape(label)}
            </div>

            <div class="metric-value">
                {html.escape(value)}
            </div>
        </article>
        """

    def _build_parameter_cards(
        self,
        analysis: ParameterStabilityAnalysis,
    ) -> str:
        if not analysis.parameters:
            return (
                '<div class="card empty-state">'
                "No parameter stability data available."
                "</div>"
            )

        cards = []

        for name, summary in analysis.parameters.items():
            frequencies = "".join(
                f"""
                <li class="frequency-item">
                    <span>{html.escape(str(value))}</span>
                    <strong>{count}</strong>
                </li>
                """
                for value, count in (
                    summary.frequencies.items()
                )
            )

            cards.append(
                f"""
                <article class="card">
                    <h3>{html.escape(name)}</h3>

                    <div class="details">
                        <div class="detail-row">
                            <span class="detail-label">
                                Dominant Value
                            </span>
                            <strong>
                                {html.escape(
                                    str(summary.dominant_value)
                                )}
                            </strong>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">
                                Dominant Count
                            </span>
                            <strong>
                                {summary.dominant_count}
                            </strong>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">
                                Dominant Rate
                            </span>
                            <strong>
                                {summary.dominant_rate:.2f}%
                            </strong>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">
                                Stability Score
                            </span>
                            <strong>
                                {summary.stability_score:.2f}
                            </strong>
                        </div>

                        <div class="detail-row">
                            <span class="detail-label">
                                Total Observations
                            </span>
                            <strong>
                                {summary.total_observations}
                            </strong>
                        </div>
                    </div>

                    <ul class="frequency-list">
                        {frequencies}
                    </ul>
                </article>
                """
            )

        return (
            '<div class="parameter-grid">'
            + "".join(cards)
            + "</div>"
        )
