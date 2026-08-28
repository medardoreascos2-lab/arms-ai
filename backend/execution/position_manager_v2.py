from __future__ import annotations

from uuid import uuid4

from backend.instruments.instrument_profile_engine import (
    InstrumentProfileEngine,
)


class PositionManagerV2:
    """
    Abre y actualiza posiciones provenientes
    de ejecuciones PAPER con estado FILLED.
    """

    VALID_SIDES = {
        "BUY",
        "SELL",
    }

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        point_value: float,
        instrument_profile_engine:
        InstrumentProfileEngine
        | None = None,
    ) -> None:
        normalized_point_value = float(
            point_value
        )

        if normalized_point_value <= 0:
            raise ValueError(
                "point_value debe ser "
                "mayor que cero."
            )

        self.point_value = (
            normalized_point_value
        )

        self.instrument_profile_engine = (
            instrument_profile_engine
            if instrument_profile_engine is not None
            else None
        )

    def _resolve_point_value(
        self,
        *,
        symbol: str,
    ) -> float:
        if self.instrument_profile_engine is None:
            return self.point_value

        profile = (
            self.instrument_profile_engine.get_profile(
                symbol=symbol,
            )
        )

        return float(
            profile["point_value"]
        )

    def open_position(
        self,
        *,
        execution: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(
            execution,
            dict,
        ):
            raise TypeError(
                "execution debe ser un dict."
            )

        accepted = bool(
            execution.get(
                "accepted",
                False,
            )
        )

        status = (
            str(
                execution.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if not accepted:
            return {
                "opened": False,
                "status": "INACTIVE",
                "reason": (
                    "execution_not_accepted"
                ),
            }

        if status != "FILLED":
            return {
                "opened": False,
                "status": "INACTIVE",
                "reason": (
                    "execution_not_filled"
                ),
            }

        side = (
            str(
                execution.get(
                    "side",
                    "",
                )
            )
            .strip()
            .upper()
        )

        symbol = (
            str(
                execution.get(
                    "symbol",
                    "",
                )
            )
            .strip()
            .upper()
        )

        point_value = (
            self._resolve_point_value(
                symbol=symbol,
            )
        )

        if side not in self.VALID_SIDES:
            raise ValueError(
                "side debe ser BUY o SELL."
            )

        filled_price_value = (
            execution.get(
                "filled_price"
            )
        )

        if filled_price_value is None:
            raise ValueError(
                "filled_price es obligatorio."
            )

        filled_price = float(
            filled_price_value
        )

        if filled_price <= 0:
            raise ValueError(
                "filled_price debe ser "
                "mayor que cero."
            )

        quantity = int(
            execution.get(
                "quantity",
                0,
            )
        )

        if quantity <= 0:
            raise ValueError(
                "quantity debe ser "
                "mayor que cero."
            )

        stop_loss = float(
            execution.get(
                "stop_loss",
                0.0,
            )
        )

        take_profit = float(
            execution.get(
                "take_profit",
                0.0,
            )
        )

        if stop_loss <= 0:
            raise ValueError(
                "stop_loss debe ser "
                "mayor que cero."
            )

        if take_profit <= 0:
            raise ValueError(
                "take_profit debe ser "
                "mayor que cero."
            )

        if side == "BUY":
            direction = "LONG"

            if stop_loss >= filled_price:
                raise ValueError(
                    "stop_loss debe estar por "
                    "debajo de filled_price "
                    "para LONG."
                )

            if take_profit <= filled_price:
                raise ValueError(
                    "take_profit debe estar por "
                    "encima de filled_price "
                    "para LONG."
                )

        else:
            direction = "SHORT"

            if stop_loss <= filled_price:
                raise ValueError(
                    "stop_loss debe estar por "
                    "encima de filled_price "
                    "para SHORT."
                )

            if take_profit >= filled_price:
                raise ValueError(
                    "take_profit debe estar por "
                    "debajo de filled_price "
                    "para SHORT."
                )

        return {
            "opened": True,
            "status": "OPEN",
            "position_id": str(
                uuid4()
            ),
            "broker_position_id": (
                execution.get(
                    "position_id"
                )
            ),
            "order_id": execution.get(
                "order_id"
            ),
            "execution_mode": (
                execution.get(
                    "execution_mode"
                )
            ),
            "symbol": symbol,
            "direction": direction,
            "quantity": quantity,
            "entry_price": (
                filled_price
            ),
            "current_price": (
                filled_price
            ),
            "stop_loss": stop_loss,
            "take_profit": (
                take_profit
            ),
            "unrealized_points": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "exit_price": None,
            "close_reason": None,
            "point_value": (
                point_value
            ),
        }

    def update_position(
        self,
        *,
        position: dict[str, object],
        current_price: float,
    ) -> dict[str, object]:
        if not isinstance(
            position,
            dict,
        ):
            raise TypeError(
                "position debe ser un dict."
            )

        position_status = (
            str(
                position.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if position_status != "OPEN":
            raise ValueError(
                "position debe estar OPEN."
            )

        normalized_current_price = float(
            current_price
        )

        if normalized_current_price <= 0:
            raise ValueError(
                "current_price debe ser "
                "mayor que cero."
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

        if (
            direction
            not in self.VALID_DIRECTIONS
        ):
            raise ValueError(
                "direction debe ser "
                "LONG o SHORT."
            )

        entry_price = float(
            position.get(
                "entry_price",
                0.0,
            )
        )

        stop_loss = float(
            position.get(
                "stop_loss",
                0.0,
            )
        )

        take_profit = float(
            position.get(
                "take_profit",
                0.0,
            )
        )

        quantity = float(
            position.get(
                "quantity",
                0.0,
            )
        )

        point_value = float(
            position.get(
                "point_value",
                self.point_value,
            )
        )

        if point_value <= 0:
            raise ValueError(
                "point_value debe ser "
                "mayor que cero."
            )

        if direction == "LONG":
            unrealized_points = (
                normalized_current_price
                - entry_price
            )

            hit_take_profit = (
                normalized_current_price
                >= take_profit
            )

            hit_stop_loss = (
                normalized_current_price
                <= stop_loss
            )

        else:
            unrealized_points = (
                entry_price
                - normalized_current_price
            )

            hit_take_profit = (
                normalized_current_price
                <= take_profit
            )

            hit_stop_loss = (
                normalized_current_price
                >= stop_loss
            )

        unrealized_points = round(
            unrealized_points,
            10,
        )

        unrealized_pnl = round(
            unrealized_points
            * quantity
            * point_value,
            10,
        )

        updated = dict(
            position
        )

        updated[
            "current_price"
        ] = normalized_current_price

        updated[
            "unrealized_points"
        ] = unrealized_points

        updated[
            "unrealized_pnl"
        ] = unrealized_pnl

        if hit_take_profit:
            updated["status"] = "CLOSED"
            updated[
                "close_reason"
            ] = "TAKE_PROFIT"
            updated[
                "exit_price"
            ] = normalized_current_price
            previous_realized_pnl = float(
                position.get(
                    "realized_pnl",
                    0.0,
                )
                or 0.0
            )

            updated[
                "realized_pnl"
            ] = round(
                previous_realized_pnl
                + unrealized_pnl,
                10,
            )

            updated[
                "total_pnl"
            ] = updated[
                "realized_pnl"
            ]

        elif hit_stop_loss:
            updated["status"] = "CLOSED"
            updated[
                "close_reason"
            ] = "STOP_LOSS"
            updated[
                "exit_price"
            ] = normalized_current_price
            previous_realized_pnl = float(
                position.get(
                    "realized_pnl",
                    0.0,
                )
                or 0.0
            )

            updated[
                "realized_pnl"
            ] = round(
                previous_realized_pnl
                + unrealized_pnl,
                10,
            )

            updated[
                "total_pnl"
            ] = updated[
                "realized_pnl"
            ]

        return updated
