from __future__ import annotations

from typing import Any

from backend.execution.position_manager import (
    PositionManager,
)


class BreakEvenEngine:
    """
    Mueve automáticamente el Stop Loss
    al precio de entrada cuando la
    operación alcanza una ganancia
    determinada.
    """

    def __init__(
        self,
        *,
        position_manager: PositionManager,
        trigger_points: float,
        offset_points: float,
    ) -> None:

        if trigger_points <= 0:
            raise ValueError(
                "trigger_points debe ser mayor que cero."
            )

        if offset_points < 0:
            raise ValueError(
                "offset_points no puede ser negativo."
            )

        self.position_manager = position_manager
        self.trigger_points = trigger_points
        self.offset_points = offset_points

    def evaluate_price(
        self,
        *,
        symbol: str,
        timeframe: str,
        current_price: float,
    ) -> dict[str, Any]:

        position = self.position_manager.get_open_position(
            symbol=symbol,
            timeframe=timeframe,
        )

        if position is None:
            return {
                "status": "NO_POSITION",
                "moved": False,
            }

        entry = float(position["entry_price"])
        stop = float(position["stop_loss"])
        side = str(position["side"])

        if side == "LONG":
            trigger = entry + self.trigger_points
            new_stop = entry + self.offset_points

            if stop >= new_stop:
                return {
                    "status": "ALREADY_PROTECTED",
                    "moved": False,
                }

            if current_price < trigger:
                return {
                    "status": "UNCHANGED",
                    "moved": False,
                }

        else:
            trigger = entry - self.trigger_points
            new_stop = entry - self.offset_points

            if stop <= new_stop:
                return {
                    "status": "ALREADY_PROTECTED",
                    "moved": False,
                }

            if current_price > trigger:
                return {
                    "status": "UNCHANGED",
                    "moved": False,
                }

        updated = (
            self.position_manager.update_stop_loss(
                symbol=symbol,
                timeframe=timeframe,
                stop_loss=new_stop,
            )
        )

        return {
            "status": "BREAK_EVEN",
            "moved": True,
            "previous_stop_loss": (
                updated["previous_stop_loss"]
            ),
            "stop_loss": float(
                updated["stop_loss"]
            ),
        }
