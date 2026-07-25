from __future__ import annotations


class TradeJournalBreakdownAnalyticsV2:

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

        result = {
            "by_symbol": {},
            "by_direction": {},
            "by_session": {},
            "by_strategy": {},
            "by_timeframe": {},
            "by_exit_reason": {},
        }

        mappings = {
            "symbol": "by_symbol",
            "direction": "by_direction",
            "session": "by_session",
            "strategy": "by_strategy",
            "timeframe": "by_timeframe",
            "exit_reason": "by_exit_reason",
        }

        for trade in trades:

            if (
                not isinstance(
                    trade,
                    dict,
                )
            ):
                continue

            if (
                str(
                    trade.get(
                        "status",
                        "",
                    )
                )
                .strip()
                .upper()
                != "CLOSED"
            ):
                continue

            pnl = float(
                trade.get(
                    "realized_pnl",
                    0.0,
                )
            )

            for field, bucket_name in mappings.items():

                value = (
                    str(
                        trade.get(
                            field,
                            "",
                        )
                    )
                    .strip()
                    .upper()
                )

                bucket = result[
                    bucket_name
                ]

                if value not in bucket:
                    bucket[value] = {
                        "total_trades": 0,
                        "winning_trades": 0,
                        "losing_trades": 0,
                        "breakeven_trades": 0,
                        "net_profit": 0.0,
                        "win_rate": 0.0,
                    }

                stats = bucket[value]

                stats[
                    "total_trades"
                ] += 1

                stats[
                    "net_profit"
                ] += pnl

                if pnl > 0:
                    stats[
                        "winning_trades"
                    ] += 1
                elif pnl < 0:
                    stats[
                        "losing_trades"
                    ] += 1
                else:
                    stats[
                        "breakeven_trades"
                    ] += 1

        for bucket in result.values():

            for stats in bucket.values():

                total = stats[
                    "total_trades"
                ]

                stats[
                    "win_rate"
                ] = (
                    (
                        stats[
                            "winning_trades"
                        ]
                        / total
                    )
                    * 100.0
                    if total
                    else 0.0
                )

        return result
