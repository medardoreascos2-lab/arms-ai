from __future__ import annotations

from copy import deepcopy
from typing import Any


class TradeHistoryStore:
    """
    Almacena operaciones cerradas por
    símbolo y temporalidad.
    """

    def __init__(
        self,
        *,
        max_trades: int = 500,
    ) -> None:
        if max_trades <= 0:
            raise ValueError(
                "max_trades debe ser mayor que cero."
            )

        self.max_trades = max_trades

        self._history: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

    def append(
        self,
        trade: dict[str, Any],
    ) -> None:
        if not isinstance(
            trade,
            dict,
        ):
            raise TypeError(
                "trade debe ser un diccionario."
            )

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
                "La operación debe estar CLOSED."
            )

        symbol = str(
            trade["symbol"]
        ).strip().upper()

        timeframe = str(
            trade["timeframe"]
        ).strip().lower()

        if not symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if not timeframe:
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        key = (
            symbol,
            timeframe,
        )

        history = self._history.setdefault(
            key,
            [],
        )

        closed_at = trade[
            "closed_at"
        ]

        history[:] = [
            existing
            for existing in history
            if existing["closed_at"]
            != closed_at
        ]

        normalized = deepcopy(
            trade
        )

        normalized["symbol"] = symbol
        normalized["timeframe"] = timeframe
        normalized["status"] = "CLOSED"
        normalized["closed"] = True

        history.append(
            normalized
        )

        history.sort(
            key=lambda item: item[
                "closed_at"
            ]
        )

        if len(history) > self.max_trades:
            del history[
                : len(history)
                - self.max_trades
            ]

    def get_history(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        key = (
            str(symbol).strip().upper(),
            str(timeframe).strip().lower(),
        )

        history = self._history.get(
            key,
            [],
        )

        return deepcopy(
            history[-limit:]
        )
