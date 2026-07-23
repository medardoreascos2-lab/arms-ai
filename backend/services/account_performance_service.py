from __future__ import annotations

from typing import Any


class AccountPerformanceService:
    """
    Calcula métricas de rendimiento
    usando operaciones cerradas.
    """

    def calculate(
        self,
        *,
        trades: list[dict[str, Any]],
        starting_balance: float,
    ) -> dict[str, object]:
        if starting_balance <= 0:
            raise ValueError(
                "starting_balance debe ser mayor que cero."
            )

        for trade in trades:
            if (
                str(
                    trade["status"]
                ).strip().upper()
                != "CLOSED"
                or not bool(
                    trade["closed"]
                )
            ):
                raise ValueError(
                    "Todas las operaciones deben estar CLOSED."
                )

        total_trades = len(
            trades
        )

        pnl_values = [
            float(
                trade["pnl"]
            )
            for trade in trades
        ]

        realized_pnl = sum(
            pnl_values
        )

        current_balance = (
            starting_balance
            + realized_pnl
        )

        winning_trades = sum(
            1
            for pnl in pnl_values
            if pnl > 0
        )

        losing_trades = sum(
            1
            for pnl in pnl_values
            if pnl < 0
        )

        breakeven_trades = sum(
            1
            for pnl in pnl_values
            if pnl == 0
        )

        win_rate = (
            winning_trades
            / total_trades
            * 100
            if total_trades > 0
            else 0.0
        )

        gross_profit = sum(
            pnl
            for pnl in pnl_values
            if pnl > 0
        )

        gross_loss = abs(
            sum(
                pnl
                for pnl in pnl_values
                if pnl < 0
            )
        )

        if total_trades == 0:
            profit_factor: float | None = 0.0
        elif gross_loss == 0:
            profit_factor = None
        else:
            profit_factor = (
                gross_profit
                / gross_loss
            )

        average_trade = (
            realized_pnl
            / total_trades
            if total_trades > 0
            else 0.0
        )

        balance = float(
            starting_balance
        )

        peak_balance = balance
        max_drawdown = 0.0
        max_drawdown_percent = 0.0

        for pnl in pnl_values:
            balance += pnl

            if balance > peak_balance:
                peak_balance = balance

            drawdown = (
                peak_balance
                - balance
            )

            drawdown_percent = (
                drawdown
                / peak_balance
                * 100
                if peak_balance > 0
                else 0.0
            )

            if drawdown > max_drawdown:
                max_drawdown = drawdown

            if (
                drawdown_percent
                > max_drawdown_percent
            ):
                max_drawdown_percent = (
                    drawdown_percent
                )

        return {
            "starting_balance": float(
                starting_balance
            ),
            "current_balance": (
                current_balance
            ),
            "realized_pnl": (
                realized_pnl
            ),
            "total_trades": total_trades,
            "winning_trades": (
                winning_trades
            ),
            "losing_trades": (
                losing_trades
            ),
            "breakeven_trades": (
                breakeven_trades
            ),
            "win_rate": win_rate,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": (
                profit_factor
            ),
            "average_trade": (
                average_trade
            ),
            "max_drawdown": (
                max_drawdown
            ),
            "max_drawdown_percent": (
                max_drawdown_percent
            ),
        }
