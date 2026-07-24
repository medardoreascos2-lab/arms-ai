from __future__ import annotations

from collections import defaultdict


class PerformanceAnalyticsV2:
    """
    Calcula métricas de rendimiento globales
    y agrupadas por símbolo, sesión,
    temporalidad y estrategia.
    """

    def __init__(
        self,
        *,
        risk_free_rate: float,
        trading_days_per_year: int,
    ) -> None:
        self.risk_free_rate = float(
            risk_free_rate
        )

        normalized_trading_days = int(
            trading_days_per_year
        )

        if normalized_trading_days <= 0:
            raise ValueError(
                "trading_days_per_year debe ser "
                "mayor que cero."
            )

        self.trading_days_per_year = (
            normalized_trading_days
        )

    @staticmethod
    def _normalize_group_value(
        value: object,
        *,
        fallback: str,
    ) -> str:
        normalized = (
            str(value)
            .strip()
            .upper()
        )

        return (
            normalized
            if normalized
            else fallback
        )

    @staticmethod
    def _validate_trades(
        trades: object,
    ) -> list[dict[str, object]]:
        if not isinstance(
            trades,
            list,
        ):
            raise TypeError(
                "trades debe ser una lista."
            )

        normalized_trades: list[
            dict[str, object]
        ] = []

        for trade in trades:
            if not isinstance(
                trade,
                dict,
            ):
                raise TypeError(
                    "Cada trade debe ser un dict."
                )

            realized_pnl_value = (
                trade.get(
                    "realized_pnl"
                )
            )

            if realized_pnl_value is None:
                raise ValueError(
                    "realized_pnl es obligatorio."
                )

            normalized_trade = dict(
                trade
            )

            normalized_trade[
                "realized_pnl"
            ] = float(
                realized_pnl_value
            )

            normalized_trade[
                "result"
            ] = (
                str(
                    trade.get(
                        "result",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            normalized_trade[
                "symbol"
            ] = (
                str(
                    trade.get(
                        "symbol",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            normalized_trade[
                "timeframe"
            ] = (
                str(
                    trade.get(
                        "timeframe",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            normalized_trade[
                "session"
            ] = (
                str(
                    trade.get(
                        "session",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            normalized_trade[
                "strategy"
            ] = (
                str(
                    trade.get(
                        "strategy",
                        "",
                    )
                )
                .strip()
                .upper()
            )

            normalized_trades.append(
                normalized_trade
            )

        return normalized_trades

    @staticmethod
    def _calculate_basic_metrics(
        trades: list[
            dict[str, object]
        ],
    ) -> dict[str, object]:
        total_trades = len(
            trades
        )

        wins = [
            trade
            for trade in trades
            if float(
                trade[
                    "realized_pnl"
                ]
            ) > 0
        ]

        losses = [
            trade
            for trade in trades
            if float(
                trade[
                    "realized_pnl"
                ]
            ) < 0
        ]

        break_even_trades = [
            trade
            for trade in trades
            if float(
                trade[
                    "realized_pnl"
                ]
            ) == 0
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
                for trade in trades
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
        }

    @classmethod
    def _group_metrics(
        cls,
        trades: list[
            dict[str, object]
        ],
        *,
        field_name: str,
        fallback: str,
    ) -> dict[str, dict[str, object]]:
        grouped: dict[
            str,
            list[dict[str, object]],
        ] = defaultdict(
            list
        )

        for trade in trades:
            group_name = (
                cls._normalize_group_value(
                    trade.get(
                        field_name
                    ),
                    fallback=fallback,
                )
            )

            grouped[
                group_name
            ].append(
                trade
            )

        return {
            group_name: (
                cls._calculate_basic_metrics(
                    group_trades
                )
            )
            for (
                group_name,
                group_trades,
            ) in grouped.items()
        }

    def analyze(
        self,
        *,
        trades: list[
            dict[str, object]
        ],
        starting_balance: float,
    ) -> dict[str, object]:
        normalized_trades = (
            self._validate_trades(
                trades
            )
        )

        normalized_starting_balance = float(
            starting_balance
        )

        if normalized_starting_balance <= 0:
            raise ValueError(
                "starting_balance debe ser "
                "mayor que cero."
            )

        metrics = (
            self._calculate_basic_metrics(
                normalized_trades
            )
        )

        equity_curve = [
            normalized_starting_balance
        ]

        current_balance = (
            normalized_starting_balance
        )

        peak_balance = (
            normalized_starting_balance
        )

        maximum_drawdown = 0.0
        maximum_drawdown_percent = 0.0

        for trade in normalized_trades:
            current_balance = round(
                current_balance
                + float(
                    trade[
                        "realized_pnl"
                    ]
                ),
                10,
            )

            equity_curve.append(
                current_balance
            )

            if current_balance > peak_balance:
                peak_balance = (
                    current_balance
                )

            drawdown = round(
                peak_balance
                - current_balance,
                10,
            )

            drawdown_percent = (
                drawdown
                / peak_balance
                if peak_balance > 0
                else 0.0
            )

            if drawdown > maximum_drawdown:
                maximum_drawdown = (
                    drawdown
                )

            if (
                drawdown_percent
                > maximum_drawdown_percent
            ):
                maximum_drawdown_percent = (
                    drawdown_percent
                )

        ending_balance = (
            equity_curve[-1]
        )

        net_pnl = float(
            metrics[
                "net_pnl"
            ]
        )

        recovery_factor = (
            round(
                net_pnl
                / maximum_drawdown,
                10,
            )
            if maximum_drawdown > 0
            else None
        )

        result = dict(
            metrics
        )

        result.update(
            {
                "starting_balance": (
                    normalized_starting_balance
                ),
                "ending_balance": (
                    ending_balance
                ),
                "equity_curve": (
                    equity_curve
                ),
                "maximum_drawdown": round(
                    maximum_drawdown,
                    10,
                ),
                "maximum_drawdown_percent": round(
                    maximum_drawdown_percent,
                    10,
                ),
                "recovery_factor": (
                    recovery_factor
                ),
                "risk_free_rate": (
                    self.risk_free_rate
                ),
                "trading_days_per_year": (
                    self.trading_days_per_year
                ),
                "by_symbol": (
                    self._group_metrics(
                        normalized_trades,
                        field_name="symbol",
                        fallback="UNKNOWN",
                    )
                ),
                "by_session": (
                    self._group_metrics(
                        normalized_trades,
                        field_name="session",
                        fallback="UNKNOWN",
                    )
                ),
                "by_timeframe": (
                    self._group_metrics(
                        normalized_trades,
                        field_name="timeframe",
                        fallback="UNKNOWN",
                    )
                ),
                "by_strategy": (
                    self._group_metrics(
                        normalized_trades,
                        field_name="strategy",
                        fallback="UNKNOWN",
                    )
                ),
            }
        )

        return result
