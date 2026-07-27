from __future__ import annotations


class TradeJournalAnalyticsV2:

    def calculate(
        self,
        *,
        trades: list[dict[str, object]],
    ) -> dict[str, object]:

        if not isinstance(
            trades,
            list,
        ):
            raise TypeError(
                "trades debe ser una lista."
            )

        closed_trades = [
            trade
            for trade in trades
            if (
                isinstance(
                    trade,
                    dict,
                )
                and str(
                    trade.get(
                        "status",
                        "",
                    )
                )
                .strip()
                .upper()
                == "CLOSED"
            )
        ]

        pnl_values = [
            float(
                trade.get(
                    "realized_pnl",
                    0.0,
                )
            )
            for trade in closed_trades
        ]

        durations = [
            float(
                trade.get(
                    "duration_seconds",
                    0.0,
                )
            )
            for trade in closed_trades
        ]

        total_trades = len(
            closed_trades
        )

        winning_values = [
            value
            for value in pnl_values
            if value > 0
        ]

        losing_values = [
            value
            for value in pnl_values
            if value < 0
        ]

        breakeven_values = [
            value
            for value in pnl_values
            if value == 0
        ]

        winning_trades = len(
            winning_values
        )

        losing_trades = len(
            losing_values
        )

        breakeven_trades = len(
            breakeven_values
        )

        gross_profit = round(
            sum(
                winning_values
            ),
            10,
        )

        gross_loss = round(
            abs(
                sum(
                    losing_values
                )
            ),
            10,
        )

        net_profit = round(
            sum(
                pnl_values
            ),
            10,
        )

        average_win = round(
            (
                gross_profit
                / winning_trades
            )
            if winning_trades
            else 0.0,
            10,
        )

        average_loss = round(
            (
                gross_loss
                / losing_trades
            )
            if losing_trades
            else 0.0,
            10,
        )

        largest_win = (
            max(
                winning_values
            )
            if winning_values
            else 0.0
        )

        largest_loss = (
            min(
                losing_values
            )
            if losing_values
            else 0.0
        )

        win_rate = round(
            (
                winning_trades
                / total_trades
                * 100.0
            )
            if total_trades
            else 0.0,
            10,
        )

        profit_factor: float | None

        if gross_profit == 0:
            profit_factor = 0.0
        elif gross_loss == 0:
            profit_factor = None
        else:
            profit_factor = round(
                gross_profit
                / gross_loss,
                10,
            )

        expectancy = round(
            (
                net_profit
                / total_trades
            )
            if total_trades
            else 0.0,
            10,
        )

        average_duration_seconds = round(
            (
                sum(
                    durations
                )
                / total_trades
            )
            if total_trades
            else 0.0,
            10,
        )

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "breakeven_trades": breakeven_trades,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "net_profit": net_profit,
            "average_win": average_win,
            "average_loss": average_loss,
            "largest_win": largest_win,
            "largest_loss": largest_loss,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "average_duration_seconds": (
                average_duration_seconds
            ),
        }
