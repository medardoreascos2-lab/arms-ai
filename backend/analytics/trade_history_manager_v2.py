from __future__ import annotations

from uuid import uuid4


class TradeHistoryManagerV2:
    """
    Registra posiciones cerradas y calcula
    métricas básicas de rendimiento.
    """

    def __init__(
        self,
    ) -> None:
        self._history: list[
            dict[str, object]
        ] = []

        self._position_ids: set[str] = set()

    def record(
        self,
        *,
        position: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(
            position,
            dict,
        ):
            raise TypeError(
                "position debe ser un dict."
            )

        status = (
            str(
                position.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if status != "CLOSED":
            return {
                "recorded": False,
                "reason": (
                    "position_not_closed"
                ),
                "trade": None,
            }

        position_id = (
            str(
                position.get(
                    "position_id",
                    "",
                )
            )
            .strip()
        )

        if not position_id:
            raise ValueError(
                "position_id es obligatorio."
            )

        if (
            position_id
            in self._position_ids
        ):
            return {
                "recorded": False,
                "reason": (
                    "duplicate_position"
                ),
                "trade": None,
            }

        realized_pnl_value = (
            position.get(
                "realized_pnl"
            )
        )

        if realized_pnl_value is None:
            raise ValueError(
                "realized_pnl es obligatorio."
            )

        realized_pnl = float(
            realized_pnl_value
        )

        if realized_pnl > 0:
            result = "WIN"
        elif realized_pnl < 0:
            result = "LOSS"
        else:
            result = "BREAK_EVEN"

        symbol = (
            str(
                position.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        direction = (
            str(
                position.get(
                    "direction",
                    "",
                )
            )
            .strip()
            .upper()
        )

        trade = {
            "trade_id": str(
                uuid4()
            ),
            "position_id": (
                position_id
            ),
            "order_id": position.get(
                "order_id"
            ),
            "execution_mode": (
                position.get(
                    "execution_mode"
                )
            ),
            "symbol": symbol,
            "direction": direction,
            "quantity": int(
                position.get(
                    "quantity",
                    0,
                )
            ),
            "entry_price": float(
                position.get(
                    "entry_price",
                    0.0,
                )
            ),
            "exit_price": float(
                position.get(
                    "exit_price",
                    0.0,
                )
            ),
            "stop_loss": float(
                position.get(
                    "stop_loss",
                    0.0,
                )
            ),
            "take_profit": float(
                position.get(
                    "take_profit",
                    0.0,
                )
            ),
            "realized_pnl": (
                realized_pnl
            ),
            "close_reason": (
                str(
                    position.get(
                        "close_reason",
                        "",
                    )
                )
                .strip()
                .upper()
            ),
            "result": result,
            "point_value": float(
                position.get(
                    "point_value",
                    0.0,
                )
            ),
        }

        self._history.append(
            trade
        )

        self._position_ids.add(
            position_id
        )

        return {
            "recorded": True,
            "reason": None,
            "trade": dict(
                trade
            ),
        }

    def get_history(
        self,
        *,
        limit: int | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, object]]:
        if limit is not None:
            normalized_limit = int(
                limit
            )

            if normalized_limit <= 0:
                raise ValueError(
                    "limit debe ser mayor "
                    "que cero."
                )
        else:
            normalized_limit = None

        history = self._history

        if symbol is not None:
            normalized_symbol = (
                str(symbol)
                .strip()
                .upper()
            )

            history = [
                trade
                for trade in history
                if trade["symbol"]
                == normalized_symbol
            ]

        if normalized_limit is not None:
            history = history[
                -normalized_limit:
            ]

        return [
            dict(
                trade
            )
            for trade in history
        ]

    def get_equity_curve(
        self,
        *,
        starting_balance: float,
    ) -> list[float]:
        normalized_balance = float(
            starting_balance
        )

        if normalized_balance <= 0:
            raise ValueError(
                "starting_balance debe ser "
                "mayor que cero."
            )

        curve = [
            normalized_balance
        ]

        current_balance = (
            normalized_balance
        )

        for trade in self._history:
            current_balance = round(
                current_balance
                + float(
                    trade[
                        "realized_pnl"
                    ]
                ),
                10,
            )

            curve.append(
                current_balance
            )

        return curve

    def calculate_metrics(
        self,
        *,
        starting_balance: float | None = None,
    ) -> dict[str, object]:
        total_trades = len(
            self._history
        )

        wins = [
            trade
            for trade in self._history
            if trade["result"] == "WIN"
        ]

        losses = [
            trade
            for trade in self._history
            if trade["result"] == "LOSS"
        ]

        break_even_trades = [
            trade
            for trade in self._history
            if trade["result"]
            == "BREAK_EVEN"
        ]

        wins_count = len(
            wins
        )

        losses_count = len(
            losses
        )

        break_even_count = len(
            break_even_trades
        )

        gross_profit = round(
            sum(
                float(
                    trade[
                        "realized_pnl"
                    ]
                )
                for trade in wins
            ),
            10,
        )

        gross_loss = round(
            abs(
                sum(
                    float(
                        trade[
                            "realized_pnl"
                        ]
                    )
                    for trade in losses
                )
            ),
            10,
        )

        net_pnl = round(
            sum(
                float(
                    trade[
                        "realized_pnl"
                    ]
                )
                for trade
                in self._history
            ),
            10,
        )

        win_rate = (
            round(
                wins_count
                / total_trades,
                4,
            )
            if total_trades > 0
            else 0.0
        )

        average_win = (
            round(
                gross_profit
                / wins_count,
                10,
            )
            if wins_count > 0
            else 0.0
        )

        average_loss = (
            round(
                gross_loss
                / losses_count,
                10,
            )
            if losses_count > 0
            else 0.0
        )

        if total_trades == 0:
            profit_factor: float | None = (
                0.0
            )
        elif gross_loss == 0:
            profit_factor = None
        else:
            profit_factor = round(
                gross_profit
                / gross_loss,
                10,
            )

        expectancy = (
            round(
                net_pnl
                / total_trades,
                10,
            )
            if total_trades > 0
            else 0.0
        )

        maximum_drawdown = 0.0
        ending_balance = None
        equity_curve = None

        if starting_balance is not None:
            equity_curve = (
                self.get_equity_curve(
                    starting_balance=(
                        starting_balance
                    ),
                )
            )

            peak = equity_curve[0]

            for balance in equity_curve:
                if balance > peak:
                    peak = balance

                drawdown = (
                    peak - balance
                )

                if (
                    drawdown
                    > maximum_drawdown
                ):
                    maximum_drawdown = (
                        drawdown
                    )

            maximum_drawdown = round(
                maximum_drawdown,
                10,
            )

            ending_balance = (
                equity_curve[-1]
            )

        return {
            "total_trades": (
                total_trades
            ),
            "wins": wins_count,
            "losses": losses_count,
            "break_even": (
                break_even_count
            ),
            "win_rate": win_rate,
            "gross_profit": (
                gross_profit
            ),
            "gross_loss": (
                gross_loss
            ),
            "net_pnl": net_pnl,
            "average_win": (
                average_win
            ),
            "average_loss": (
                average_loss
            ),
            "profit_factor": (
                profit_factor
            ),
            "expectancy": expectancy,
            "maximum_drawdown": (
                maximum_drawdown
            ),
            "ending_balance": (
                ending_balance
            ),
            "equity_curve": (
                equity_curve
            ),
        }
