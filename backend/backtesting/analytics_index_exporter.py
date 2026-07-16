import html
from pathlib import Path


class AnalyticsIndexExporter:
    """
    Genera una página índice para acceder a todos los
    dashboards analíticos de ARMS AI.
    """

    def export_html(
        self,
        file_path: str | Path,
        backtest_dashboard: str | Path | None = None,
        walk_forward_dashboard: str | Path | None = None,
        optimization_dashboard: str | Path | None = None,
        parameter_stability_dashboard: str | Path | None = None,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            self._build_html(
                backtest_dashboard=backtest_dashboard,
                walk_forward_dashboard=walk_forward_dashboard,
                optimization_dashboard=optimization_dashboard,
                parameter_stability_dashboard=(
                    parameter_stability_dashboard
                ),
            ),
            encoding="utf-8",
        )

        return path

    def _build_html(
        self,
        backtest_dashboard: str | Path | None,
        walk_forward_dashboard: str | Path | None,
        optimization_dashboard: str | Path | None,
        parameter_stability_dashboard: str | Path | None,
    ) -> str:
        cards = [
            self._dashboard_card(
                title="Backtest",
                description=(
                    "Resultados generales, estadísticas, "
                    "curva de capital y operaciones."
                ),
                link=backtest_dashboard,
            ),
            self._dashboard_card(
                title="Walk Forward",
                description=(
                    "Rendimiento fuera de muestra por ventanas "
                    "y estabilidad temporal."
                ),
                link=walk_forward_dashboard,
            ),
            self._dashboard_card(
                title="Optimization",
                description=(
                    "Comparación training vs testing, "
                    "degradación y señales de overfitting."
                ),
                link=optimization_dashboard,
            ),
            self._dashboard_card(
                title="Parameter Stability",
                description=(
                    "Frecuencia, valores dominantes y "
                    "estabilidad de los parámetros."
                ),
                link=parameter_stability_dashboard,
            ),
        ]

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>ARMS AI Analytics</title>

    <style>
        :root {{
            color-scheme: dark;
            --background: #07111f;
            --surface: #0f1b2d;
            --surface-light: #17263b;
            --border: #2b3d55;
            --text: #f8fafc;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --disabled: #64748b;
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background:
                radial-gradient(
                    circle at top,
                    #11253f 0%,
                    var(--background) 42%
                );
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
            width: min(1180px, calc(100% - 32px));
            margin: 0 auto;
            padding: 48px 0 72px;
        }}

        header {{
            margin-bottom: 32px;
        }}

        h1 {{
            margin: 0 0 10px;
            font-size: clamp(34px, 6vw, 56px);
        }}

        .subtitle {{
            max-width: 760px;
            color: var(--muted);
            font-size: 17px;
            line-height: 1.7;
        }}

        .grid {{
            display: grid;
            grid-template-columns:
                repeat(auto-fit, minmax(260px, 1fr));
            gap: 18px;
        }}

        .card {{
            display: flex;
            flex-direction: column;
            min-height: 220px;
            padding: 22px;
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow:
                0 10px 28px rgba(0, 0, 0, 0.22);
        }}

        .card h2 {{
            margin: 0 0 12px;
            font-size: 22px;
        }}

        .card p {{
            margin: 0 0 24px;
            color: var(--muted);
            line-height: 1.6;
        }}

        .card-footer {{
            margin-top: auto;
        }}

        .button {{
            display: inline-block;
            padding: 11px 16px;
            border-radius: 9px;
            background: var(--surface-light);
            border: 1px solid var(--border);
            color: var(--accent);
            text-decoration: none;
            font-weight: 700;
        }}

        .button:hover {{
            border-color: var(--accent);
        }}

        .status {{
            color: var(--disabled);
            font-weight: 700;
        }}

        footer {{
            margin-top: 34px;
            color: var(--muted);
            font-size: 13px;
        }}
    </style>
</head>

<body>
    <main class="container">
        <header>
            <h1>ARMS AI Analytics</h1>

            <div class="subtitle">
                Central analytics hub for backtesting,
                walk-forward validation, optimization and
                parameter stability.
            </div>
        </header>

        <section class="grid">
            {''.join(cards)}
        </section>

        <footer>
            Generated automatically by ARMS AI.
        </footer>
    </main>
</body>
</html>
"""

    def _dashboard_card(
        self,
        title: str,
        description: str,
        link: str | Path | None,
    ) -> str:
        if link is None:
            action = (
                '<span class="status">'
                "Not generated yet"
                "</span>"
            )
        else:
            normalized_link = str(link).replace(
                "\\",
                "/",
            )

            action = (
                f'<a class="button" '
                f'href="{html.escape(normalized_link)}">'
                "Open dashboard"
                "</a>"
            )

        return f"""
        <article class="card">
            <h2>{html.escape(title)}</h2>

            <p>{html.escape(description)}</p>

            <div class="card-footer">
                {action}
            </div>
        </article>
        """
