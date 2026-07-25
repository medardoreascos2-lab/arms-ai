from __future__ import annotations


from backend.analytics.trade_journal_analytics_v2 import (
    TradeJournalAnalyticsV2,
)


from copy import deepcopy
from datetime import datetime


class TradeJournalV2:

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    REQUIRED_FIELDS = (
        "trade_id",
        "position_id",
        "symbol",
        "direction",
        "entry_price",
        "quantity",
        "entry_time",
    )

    def __init__(
        self,
        *,
        analytics_v2:
        TradeJournalAnalyticsV2
        | None = None,
    ) -> None:
        if (
            analytics_v2
            is not None
            and not isinstance(
                analytics_v2,
                TradeJournalAnalyticsV2,
            )
        ):
            raise TypeError(
                "analytics_v2 debe ser "
                "TradeJournalAnalyticsV2."
            )

        self.analytics_v2 = (
            analytics_v2
        )

        self._open_trades: dict[
            str,
            dict[str, object],
        ] = {}

        self._closed_trades: list[
            dict[str, object]
        ] = []

    def record_open_trade(
        self,
        *,
        trade: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(
            trade,
            dict,
        ):
            raise TypeError(
                "trade debe ser un dict."
            )

        for field in self.REQUIRED_FIELDS:
            value = trade.get(
                field
            )

            if value is None or (
                isinstance(
                    value,
                    str,
                )
                and not value.strip()
            ):
                raise ValueError(
                    f"{field} es obligatorio."
                )

        trade_id = str(
            trade[
                "trade_id"
            ]
        ).strip()

        if (
            trade_id
            in self._open_trades
            or any(
                str(
                    item.get(
                        "trade_id",
                        "",
                    )
                )
                == trade_id
                for item in self._closed_trades
            )
        ):
            raise ValueError(
                "trade_id duplicado."
            )

        direction = str(
            trade[
                "direction"
            ]
        ).strip().upper()

        if (
            direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "direction debe ser LONG o SHORT."
            )

        entry_price = float(
            trade[
                "entry_price"
            ]
        )

        if entry_price <= 0:
            raise ValueError(
                "entry_price debe ser mayor que cero."
            )

        quantity = float(
            trade[
                "quantity"
            ]
        )

        if quantity <= 0:
            raise ValueError(
                "quantity debe ser mayor que cero."
            )

        entry_time = trade[
            "entry_time"
        ]

        if not isinstance(
            entry_time,
            datetime,
        ):
            raise ValueError(
                "entry_time debe ser datetime."
            )

        normalized_trade = deepcopy(
            trade
        )

        normalized_trade[
            "trade_id"
        ] = trade_id

        normalized_trade[
            "position_id"
        ] = str(
            trade[
                "position_id"
            ]
        ).strip()

        normalized_trade[
            "symbol"
        ] = str(
            trade[
                "symbol"
            ]
        ).strip().upper()

        normalized_trade[
            "direction"
        ] = direction

        normalized_trade[
            "entry_price"
        ] = entry_price

        normalized_trade[
            "quantity"
        ] = quantity

        normalized_trade[
            "status"
        ] = "OPEN"

        self._open_trades[
            trade_id
        ] = normalized_trade

        return {
            "recorded": True,
            "status": "OPEN",
            "trade_id": trade_id,
            "trade": deepcopy(
                normalized_trade
            ),
        }

    def update_trade(
        self,
        *,
        trade_id: str,
        updates: dict[str, object],
    ) -> dict[str, object]:
        normalized_trade_id = str(
            trade_id
        ).strip()

        if (
            normalized_trade_id
            not in self._open_trades
        ):
            raise KeyError(
                "trade_id"
            )

        if not isinstance(
            updates,
            dict,
        ):
            raise TypeError(
                "updates debe ser un dict."
            )

        self._open_trades[
            normalized_trade_id
        ].update(
            deepcopy(
                updates
            )
        )

        return {
            "updated": True,
            "trade": deepcopy(
                self._open_trades[
                    normalized_trade_id
                ]
            ),
        }

    def close_trade(
        self,
        *,
        trade_id: str,
        exit_price: float,
        exit_time: datetime,
        exit_reason: str,
        point_value: float,
    ) -> dict[str, object]:
        normalized_trade_id = str(
            trade_id
        ).strip()

        if (
            normalized_trade_id
            not in self._open_trades
        ):
            raise KeyError(
                "trade_id"
            )

        normalized_exit_price = float(
            exit_price
        )

        if normalized_exit_price <= 0:
            raise ValueError(
                "exit_price debe ser mayor que cero."
            )

        normalized_point_value = float(
            point_value
        )

        if normalized_point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        if not isinstance(
            exit_time,
            datetime,
        ):
            raise ValueError(
                "exit_time debe ser datetime."
            )

        trade = deepcopy(
            self._open_trades[
                normalized_trade_id
            ]
        )

        entry_time = trade[
            "entry_time"
        ]

        if (
            not isinstance(
                entry_time,
                datetime,
            )
            or exit_time < entry_time
        ):
            raise ValueError(
                "exit_time no puede ser anterior a entry_time."
            )

        entry_price = float(
            trade[
                "entry_price"
            ]
        )

        quantity = float(
            trade[
                "quantity"
            ]
        )

        direction = str(
            trade[
                "direction"
            ]
        ).strip().upper()

        if direction == "LONG":
            realized_points = (
                normalized_exit_price
                - entry_price
            )
        else:
            realized_points = (
                entry_price
                - normalized_exit_price
            )

        realized_pnl = round(
            realized_points
            * quantity
            * normalized_point_value,
            10,
        )

        duration_seconds = (
            exit_time
            - entry_time
        ).total_seconds()

        trade[
            "exit_price"
        ] = normalized_exit_price

        trade[
            "exit_time"
        ] = exit_time

        trade[
            "exit_reason"
        ] = str(
            exit_reason
        ).strip().upper()

        trade[
            "point_value"
        ] = normalized_point_value

        trade[
            "realized_points"
        ] = round(
            realized_points,
            10,
        )

        trade[
            "realized_pnl"
        ] = realized_pnl

        trade[
            "duration_seconds"
        ] = duration_seconds

        trade[
            "status"
        ] = "CLOSED"

        self._open_trades.pop(
            normalized_trade_id
        )

        self._closed_trades.append(
            trade
        )

        return {
            "closed": True,
            "status": "CLOSED",
            "trade": deepcopy(
                trade
            ),
        }

    def get_trade(
        self,
        *,
        trade_id: str,
    ) -> dict[str, object]:
        normalized_trade_id = str(
            trade_id
        ).strip()

        if (
            normalized_trade_id
            in self._open_trades
        ):
            return deepcopy(
                self._open_trades[
                    normalized_trade_id
                ]
            )

        for trade in self._closed_trades:
            if (
                str(
                    trade.get(
                        "trade_id",
                        "",
                    )
                )
                == normalized_trade_id
            ):
                return deepcopy(
                    trade
                )

        raise KeyError(
            "trade_id"
        )

    def get_open_trades(
        self,
    ) -> list[dict[str, object]]:
        return deepcopy(
            list(
                self._open_trades.values()
            )
        )

    def get_closed_trades(
        self,
    ) -> list[dict[str, object]]:
        return deepcopy(
            self._closed_trades
        )

    def get_analytics(
        self,
    ) -> dict[str, object] | None:
        if self.analytics_v2 is None:
            return None

        return self.analytics_v2.calculate(
            trades=self.get_closed_trades(),
        )

    def get_summary(
        self,
    ) -> dict[str, object]:
        total_realized_pnl = round(
            sum(
                float(
                    trade.get(
                        "realized_pnl",
                        0.0,
                    )
                )
                for trade
                in self._closed_trades
            ),
            10,
        )

        winning_trades = sum(
            1
            for trade
            in self._closed_trades
            if float(
                trade.get(
                    "realized_pnl",
                    0.0,
                )
            )
            > 0
        )

        losing_trades = sum(
            1
            for trade
            in self._closed_trades
            if float(
                trade.get(
                    "realized_pnl",
                    0.0,
                )
            )
            < 0
        )

        closed_count = len(
            self._closed_trades
        )

        win_rate = (
            round(
                (
                    winning_trades
                    / closed_count
                )
                * 100.0,
                10,
            )
            if closed_count
            else 0.0
        )

        return {
            "open_trades": len(
                self._open_trades
            ),
            "closed_trades": (
                closed_count
            ),
            "winning_trades": (
                winning_trades
            ),
            "losing_trades": (
                losing_trades
            ),
            "total_realized_pnl": (
                total_realized_pnl
            ),
            "win_rate": win_rate,
            "analytics": (
                self.get_analytics()
            ),
        }
