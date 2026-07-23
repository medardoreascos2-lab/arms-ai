from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


class PositionManager:
    """
    Administra posiciones abiertas
    en modo simulado.
    """

    def __init__(self) -> None:
        self._positions: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

    def open_position(
        self,
        trade: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = str(
            trade["symbol"]
        ).strip().upper()

        timeframe = str(
            trade["timeframe"]
        ).strip().lower()

        action = str(
            trade["action"]
        ).strip().upper()

        if action not in {
            "BUY",
            "SELL",
        }:
            raise ValueError(
                "action inválida."
            )

        key = (
            symbol,
            timeframe,
        )

        if key in self._positions:
            raise ValueError(
                "Ya existe una posición abierta."
            )

        position = {
            "symbol": symbol,
            "timeframe": timeframe,
            "side": (
                "LONG"
                if action == "BUY"
                else "SHORT"
            ),
            "status": "OPEN",
            "entry_price": float(
                trade["entry_price"]
            ),
            "stop_loss": float(
                trade["stop_loss"]
            ),
            "take_profit": float(
                trade["take_profit"]
            ),
            "contracts": int(
                trade["contracts"]
            ),
            "opened_at": trade[
                "executed_at"
            ],
        }

        self._positions[key] = deepcopy(
            position
        )

        return deepcopy(position)

    def get_open_position(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any] | None:
        key = (
            symbol.strip().upper(),
            timeframe.strip().lower(),
        )

        position = self._positions.get(
            key
        )

        if position is None:
            return None

        return deepcopy(position)

    def close_position(
        self,
        *,
        symbol: str,
        timeframe: str,
        exit_price: float,
        closed_at: datetime,
        reason: str,
    ) -> dict[str, Any]:
        key = (
            symbol.strip().upper(),
            timeframe.strip().lower(),
        )

        if key not in self._positions:
            raise ValueError(
                "No existe una posición abierta."
            )

        position = self._positions.pop(
            key
        )

        entry = position[
            "entry_price"
        ]

        if position["side"] == "LONG":
            pnl_points = (
                exit_price - entry
            )
        else:
            pnl_points = (
                entry - exit_price
            )

        pnl = (
            pnl_points
            * position["contracts"]
            * 2.0
        )

        closed = deepcopy(
            position
        )

        closed["status"] = "CLOSED"
        closed["closed"] = True
        closed["exit_price"] = exit_price
        closed["closed_at"] = closed_at
        closed["close_reason"] = reason
        closed["pnl_points"] = pnl_points
        closed["pnl"] = pnl

        return closed
