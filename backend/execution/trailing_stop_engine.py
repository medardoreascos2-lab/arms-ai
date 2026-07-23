from __future__ import annotations

from backend.execution.position_manager import (
    PositionManager,
)


class TrailingStopEngine:
    """
    Mueve el Stop Loss siguiendo el precio
    únicamente a favor de la operación.
    """

    def __init__(
        self,
        *,
        position_manager: PositionManager,
        activation_points: float,
        distance_points: float,
    ) -> None:
        if activation_points <= 0:
            raise ValueError(
                "activation_points debe ser mayor que cero."
            )

        if distance_points <= 0:
            raise ValueError(
                "distance_points debe ser mayor que cero."
            )

        self.position_manager = position_manager
        self.activation_points = float(
            activation_points
        )
        self.distance_points = float(
            distance_points
        )

    def evaluate_price(
        self,
        *,
        symbol: str,
        timeframe: str,
        current_price: float,
    ) -> dict[str, object]:

        position = (
            self.position_manager.get_open_position(
                symbol=symbol,
                timeframe=timeframe,
            )
        )

        if position is None:
            return {
                "status": "NO_POSITION",
                "moved": False,
            }

        side = str(
            position["side"]
        ).strip().upper()

        entry = float(
            position["entry_price"]
        )

        current_stop = float(
            position["stop_loss"]
        )

        if side == "LONG":

            if (
                current_price
                < entry + self.activation_points
            ):
                return {
                    "status": "INACTIVE",
                    "moved": False,
                }

            new_stop = (
                current_price
                - self.distance_points
            )

            if new_stop <= current_stop:
                return {
                    "status": "UNCHANGED",
                    "moved": False,
                    "stop_loss": current_stop,
                }

        elif side == "SHORT":

            if (
                current_price
                > entry - self.activation_points
            ):
                return {
                    "status": "INACTIVE",
                    "moved": False,
                }

            new_stop = (
                current_price
                + self.distance_points
            )

            if new_stop >= current_stop:
                return {
                    "status": "UNCHANGED",
                    "moved": False,
                    "stop_loss": current_stop,
                }

        else:
            raise ValueError(
                "side inválido."
            )

        updated = (
            self.position_manager.update_stop_loss(
                symbol=symbol,
                timeframe=timeframe,
                stop_loss=new_stop,
            )
        )

        return {
            "status": "TRAILING_STOP",
            "moved": True,
            "previous_stop_loss": (
                updated["previous_stop_loss"]
            ),
            "stop_loss": float(
                updated["stop_loss"]
            ),
        }
