import html
import json
from pathlib import Path
from typing import Any

from backend.models.backtest_result import BacktestResult


class BacktestDashboardExporter:
    """
    Genera un dashboard HTML estático para visualizar
    los resultados de un backtest.
    """

    def export_html(
        self,
        result: BacktestResult,
        file_path: str | Path,
        source_file: str | Path | None = None,
        journal_path: str | Path | None = None,
        equity_path: str | Path | None = None,
        summary_path: str | Path | None = None,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        document = self._build_html(
            result=result,
            source_file=source_file,
            journal_path=journal_path,
            equity_path=equity_path,
            summary_path=summary_path,
        )

        path.write_text(
            document,
            encoding="utf-8",
        )

        return path

    def _build_html(
        self,
        result: BacktestResult,
        source_file: str | Path | None,
        journal_path: str | Path | None,
        equity_path: str | Path | None,
        summary_path: str | Path | None,
    ) -> str:
        statistics = result.statistics
        equity_curve = result.equity_curve

        balances = [
            equity_curve.initial_balance,
            *[
                point.balance
                for point in equity_curve.points
            ],
        ]

        labels = list(
            range(len(balances))
        )

        symbol = self._get_symbol(result)
        trade_rows = self._build_trade_rows(
            result.trades
        )
        report_links = self._build_report_links(
            journal_path=journal_path,
            equity_path=equity_path,
            summary_path=summary_path,
        )

        source_label = (
            self._normalize_path(source_file)
            if source_file is not None
            else "No especificado"
        )

        profit_factor = (
            "N/A"
            if statistics.profit_factor is None
            else f"{statistics.profit_factor:.2f}"
        )

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >
    <title>ARMS AI Backtest Dashboard</title>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        :root {{
            color-scheme: dark;
            --background: #0b1220;
            --surface: #111827;
            --surface-light: #1f2937;
            --border: #334155;
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
            font-size: clamp(28px, 5vw, 44px);
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

        .chart-wrapper {{
            height: 360px;
        }}

        .section {{
            margin-top: 24px;
        }}

        .table-wrapper {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            min-width: 850px;
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

        a {{
            color: var(--accent);
            text-decoration: none;
        }}

        a:hover {{
            text-decoration: underline;
        }}

        .report-links {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .report-link {{
            display: inline-block;
            padding: 10px 14px;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: var(--surface-light);
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
            <h1>ARMS AI Backtest Dashboard</h1>

            <div class="subtitle">
                Activo: {html.escape(symbol)}
                <br>
                Fuente: {html.escape(source_label)}
            </div>
        </header>

        <section class="grid">
            {self._metric_card(
                "Balance inicial",
                f"${equity_curve.initial_balance:.2f}",
            )}

            {self._metric_card(
                "Balance final",
                f"${equity_curve.balance:.2f}",
                positive=equity_curve.balance
                >= equity_curve.initial_balance,
            )}

            {self._metric_card(
                "Beneficio neto",
                f"${statistics.net_profit:.2f}",
                positive=statistics.net_profit >= 0,
            )}

            {self._metric_card(
                "Win rate",
                f"{statistics.win_rate:.2f}%",
            )}

            {self._metric_card(
                "Profit factor",
                profit_factor,
            )}

            {self._metric_card(
                "Drawdown máximo",
                f"${equity_curve.max_drawdown:.2f}",
                positive=False,
            )}

            {self._metric_card(
                "Operaciones",
                str(statistics.total_trades),
            )}

            {self._metric_card(
                "Expectativa",
                f"${statistics.expectancy:.2f}",
                positive=statistics.expectancy >= 0,
            )}
        </section>

        <section class="card section">
            <h2>Curva de equity</h2>

            <div class="chart-wrapper">
                <canvas id="equity-chart"></canvas>
            </div>
        </section>

        <section class="card section">
            <h2>Resumen de ejecución</h2>

            <div class="grid">
                {self._metric_card(
                    "Velas procesadas",
                    str(result.total_candles),
                )}

                {self._metric_card(
                    "Señales evaluadas",
                    str(result.total_signals),
                )}

                {self._metric_card(
                    "Autorizadas",
                    str(result.authorized_trades),
                )}

                {self._metric_card(
                    "Bloqueadas",
                    str(result.blocked_signals),
                )}

                {self._metric_card(
                    "Ganadoras",
                    str(statistics.winning_trades),
                )}

                {self._metric_card(
                    "Perdedoras",
                    str(statistics.losing_trades),
                )}
            </div>
        </section>

        <section class="card section">
            <h2>Operaciones</h2>

            {trade_rows}
        </section>

        <section class="card section">
            <h2>Reportes</h2>

            {report_links}
        </section>

        <footer>
            Generado automáticamente por ARMS AI.
        </footer>
    </main>

    <script>
        const labels = {json.dumps(labels)};
        const balances = {json.dumps(balances)};

        const context = document
            .getElementById("equity-chart")
            .getContext("2d");

        new Chart(context, {{
            type: "line",
            data: {{
                labels,
                datasets: [
                    {{
                        label: "Balance",
                        data: balances,
                        borderWidth: 2,
                        tension: 0.25,
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
                            text: "Número de operación",
                        }},
                    }},
                    y: {{
                        title: {{
                            display: true,
                            text: "Balance",
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

    def _build_trade_rows(
        self,
        trades: list[Any],
    ) -> str:
        if not trades:
            return (
                '<div class="empty-state">'
                "No hay operaciones registradas."
                "</div>"
            )

        rows = []

        for index, trade in enumerate(
            trades,
            start=1,
        ):
            pnl = float(
                getattr(trade, "pnl", 0.0)
            )

            pnl_class = (
                "positive"
                if pnl >= 0
                else "negative"
            )

            rows.append(
                f"""
                <tr>
                    <td>{index}</td>
                    <td>{html.escape(str(
                        getattr(trade, "symbol", "")
                    ))}</td>
                    <td>{html.escape(str(
                        getattr(trade, "timeframe", "")
                    ))}</td>
                    <td>{html.escape(str(
                        getattr(trade, "direction", "")
                    ))}</td>
                    <td>${float(
                        getattr(trade, "entry_price", 0.0)
                    ):.2f}</td>
                    <td>${float(
                        getattr(trade, "stop_loss", 0.0)
                    ):.2f}</td>
                    <td>${float(
                        getattr(trade, "take_profit", 0.0)
                    ):.2f}</td>
                    <td>${float(
                        getattr(trade, "exit_price", 0.0)
                    ):.2f}</td>
                    <td>{html.escape(str(
                        getattr(trade, "result", "")
                    ))}</td>
                    <td>{int(
                        getattr(trade, "contracts", 0)
                    )}</td>
                    <td class="{pnl_class}">
                        ${pnl:.2f}
                    </td>
                </tr>
                """
            )

        return f"""
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Símbolo</th>
                        <th>Timeframe</th>
                        <th>Dirección</th>
                        <th>Entrada</th>
                        <th>Stop</th>
                        <th>Objetivo</th>
                        <th>Salida</th>
                        <th>Resultado</th>
                        <th>Contratos</th>
                        <th>PnL</th>
                    </tr>
                </thead>

                <tbody>
                    {''.join(rows)}
                </tbody>
            </table>
        </div>
        """

    def _build_report_links(
        self,
        journal_path: str | Path | None,
        equity_path: str | Path | None,
        summary_path: str | Path | None,
    ) -> str:
        links = []

        report_values = [
            (
                "Trade Journal CSV",
                journal_path,
            ),
            (
                "Equity Curve CSV",
                equity_path,
            ),
            (
                "Backtest Summary JSON",
                summary_path,
            ),
        ]

        for label, value in report_values:
            if value is None:
                continue

            normalized_path = self._normalize_path(
                value
            )

            links.append(
                f"""
                <a
                    class="report-link"
                    href="{html.escape(normalized_path)}"
                >
                    {html.escape(label)}
                </a>
                """
            )

        if not links:
            return (
                '<div class="empty-state">'
                "No hay reportes vinculados."
                "</div>"
            )

        return (
            '<div class="report-links">'
            + "".join(links)
            + "</div>"
        )

    def _get_symbol(
        self,
        result: BacktestResult,
    ) -> str:
        if not result.trades:
            return "Sin operaciones"

        return str(
            getattr(
                result.trades[0],
                "symbol",
                "Sin símbolo",
            )
        )

    def _normalize_path(
        self,
        value: str | Path,
    ) -> str:
        return str(value).replace("\\", "/")
