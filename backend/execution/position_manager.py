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

    def reduce_position(
        self,
        *,
        symbol: str,
        timeframe: str,
        contracts_to_close: int,
        exit_price: float,
        point_value: float,
    ) -> dict[str, Any]:
        if contracts_to_close <= 0:
            raise ValueError(
                "contracts_to_close debe ser mayor que cero."
            )

        if point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        key = (
            str(symbol).strip().upper(),
            str(timeframe).strip().lower(),
        )

        position = self._positions.get(
            key
        )

        if position is None:
            raise ValueError(
                "No existe una posición abierta."
            )

        current_contracts = int(
            position["contracts"]
        )

        if contracts_to_close >= current_contracts:
            raise ValueError(
                "La reducción debe ser parcial."
            )

        entry_price = float(
            position["entry_price"]
        )

        side = str(
            position["side"]
        ).strip().upper()

        normalized_exit_price = float(
            exit_price
        )

        if side == "LONG":
            pnl_points = (
                normalized_exit_price
                - entry_price
            )
        elif side == "SHORT":
            pnl_points = (
                entry_price
                - normalized_exit_price
            )
        else:
            raise ValueError(
                "side inválido."
            )

        contracts_remaining = (
            current_contracts
            - contracts_to_close
        )

        realized_pnl = (
            pnl_points
            * contracts_to_close
            * float(point_value)
        )

        position["contracts"] = (
            contracts_remaining
        )

        return {
            "symbol": position["symbol"],
            "timeframe": position["timeframe"],
            "side": position["side"],
            "status": "PARTIAL",
            "exit_price": (
                normalized_exit_price
            ),
            "contracts_closed": (
                contracts_to_close
            ),
            "contracts_remaining": (
                contracts_remaining
            ),
            "pnl_points": pnl_points,
            "realized_pnl": realized_pnl,
        }


    def update_stop_loss(
        self,
        *,
        symbol: str,
        timeframe: str,
        stop_loss: float,
    ) -> dict[str, Any]:
        key = (
            str(symbol).strip().upper(),
            str(timeframe).strip().lower(),
        )

        position = self._positions.get(
            key
        )

        if position is None:
            raise ValueError(
                "No existe una posición abierta."
            )

        new_stop = float(
            stop_loss
        )

        entry_price = float(
            position["entry_price"]
        )

        take_profit = float(
            position["take_profit"]
        )

        side = str(
            position["side"]
        ).strip().upper()

        if side == "LONG":
            if new_stop >= take_profit:
                raise ValueError(
                    "stop_loss debe estar por debajo "
                    "del take_profit."
                )
        elif side == "SHORT":
            if new_stop <= take_profit:
                raise ValueError(
                    "stop_loss debe estar por encima "
                    "del take_profit."
                )
        else:
            raise ValueError(
                "side inválido."
            )

        previous_stop_loss = float(
            position["stop_loss"]
        )

        position["stop_loss"] = new_stop

        return {
            **deepcopy(position),
            "previous_stop_loss": (
                previous_stop_loss
            ),
            "entry_price": entry_price,
        }


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
