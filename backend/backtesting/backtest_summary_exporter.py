import json
from pathlib import Path
from typing import Any

from backend.models.backtest_result import BacktestResult


class BacktestSummaryExporter:
    """
    Exporta un resumen completo del backtest en formato JSON.
    """

    def export_json(
        self,
        result: BacktestResult,
        file_path: str | Path,
        source_file: str | Path | None = None,
        journal_path: str | Path | None = None,
        equity_path: str | Path | None = None,
    ) -> Path:
        path = Path(file_path)

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = self._build_payload(
            result=result,
            source_file=source_file,
            journal_path=journal_path,
            equity_path=equity_path,
        )

        path.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        return path

    def _build_payload(
        self,
        result: BacktestResult,
        source_file: str | Path | None,
        journal_path: str | Path | None,
        equity_path: str | Path | None,
    ) -> dict[str, Any]:
        statistics = result.statistics
        equity_curve = result.equity_curve

        return {
            "source_file": self._normalize_path(
                source_file
            ),
            "backtest": {
                "total_candles": result.total_candles,
                "total_signals": result.total_signals,
                "authorized_trades": (
                    result.authorized_trades
                ),
                "blocked_signals": result.blocked_signals,
                "registered_trades": len(
                    result.trades
                ),
            },
            "equity": {
                "initial_balance": self._round_value(
                    equity_curve.initial_balance
                ),
                "final_balance": self._round_value(
                    equity_curve.balance
                ),
                "peak_balance": self._round_value(
                    equity_curve.peak_balance
                ),
                "max_drawdown": self._round_value(
                    equity_curve.max_drawdown
                ),
            },
            "statistics": {
                "total_trades": statistics.total_trades,
                "winning_trades": (
                    statistics.winning_trades
                ),
                "losing_trades": (
                    statistics.losing_trades
                ),
                "breakeven_trades": (
                    statistics.breakeven_trades
                ),
                "gross_profit": self._round_value(
                    statistics.gross_profit
                ),
                "gross_loss": self._round_value(
                    statistics.gross_loss
                ),
                "net_profit": self._round_value(
                    statistics.net_profit
                ),
                "win_rate": self._round_value(
                    statistics.win_rate
                ),
                "profit_factor": self._round_value(
                    statistics.profit_factor
                ),
                "expectancy": self._round_value(
                    statistics.expectancy
                ),
                "max_drawdown": self._round_value(
                    statistics.max_drawdown
                ),
            },
            "reports": {
                "trade_journal": self._normalize_path(
                    journal_path
                ),
                "equity_curve": self._normalize_path(
                    equity_path
                ),
            },
        }

    def _normalize_path(
        self,
        value: str | Path | None,
    ) -> str | None:
        if value is None:
            return None

        return str(value).replace("\\", "/")

    def _round_value(
        self,
        value: Any,
    ) -> Any:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return round(float(value), 2)

        return value
