from __future__ import annotations

from copy import deepcopy


class TrailingStopEngineV2:
    """
    Mueve el stop loss a favor de una posición
    cuando se alcanza la ganancia mínima configurada.
    """

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        activation_profit_points: float,
        trailing_distance_points: float,
    ) -> None:
        normalized_activation = float(
            activation_profit_points
        )

        normalized_distance = float(
            trailing_distance_points
        )

        if normalized_activation <= 0:
            raise ValueError(
                "activation_profit_points debe ser "
                "mayor que cero."
            )

        if normalized_distance <= 0:
            raise ValueError(
                "trailing_distance_points debe ser "
                "mayor que cero."
            )

        self.activation_profit_points = (
            normalized_activation
        )

        self.trailing_distance_points = (
            normalized_distance
        )

    def apply(
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

        if status != "OPEN":
            return {
                "activated": False,
                "status": "INACTIVE",
                "reason": "position_not_open",
            }

        entry_price_value = position.get(
            "entry_price"
        )

        if entry_price_value is None:
            raise ValueError(
                "entry_price es obligatorio."
            )

        entry_price = float(
            entry_price_value
        )

        if entry_price <= 0:
            raise ValueError(
                "entry_price debe ser "
                "mayor que cero."
            )

        stop_loss_value = position.get(
            "stop_loss"
        )

        if stop_loss_value is None:
            raise ValueError(
                "stop_loss es obligatorio."
            )

        stop_loss = float(
            stop_loss_value
        )

        if direction == "LONG":
            favorable_points = round(
                normalized_current_price
                - entry_price,
                10,
            )

            proposed_stop = round(
                normalized_current_price
                - self.trailing_distance_points,
                10,
            )

        else:
            favorable_points = round(
                entry_price
                - normalized_current_price,
                10,
            )

            proposed_stop = round(
                normalized_current_price
                + self.trailing_distance_points,
                10,
            )

        if (
            favorable_points
            < self.activation_profit_points
        ):
            return {
                "activated": False,
                "status": "WAITING",
                "reason": (
                    "activation_not_reached"
                ),
                "direction": direction,
                "previous_stop_loss": (
                    stop_loss
                ),
                "new_stop_loss": (
                    stop_loss
                ),
                "activation_profit_points": (
                    self.activation_profit_points
                ),
                "trailing_distance_points": (
                    self.trailing_distance_points
                ),
                "favorable_points": (
                    favorable_points
                ),
                "position": deepcopy(
                    position
                ),
            }

        if direction == "LONG":
            stop_would_move_backward = (
                proposed_stop
                <= stop_loss
            )
        else:
            stop_would_move_backward = (
                proposed_stop
                >= stop_loss
            )

        if stop_would_move_backward:
            return {
                "activated": False,
                "status": "ALREADY_PROTECTED",
                "reason": (
                    "stop_would_move_backward"
                ),
                "direction": direction,
                "previous_stop_loss": (
                    stop_loss
                ),
                "new_stop_loss": (
                    stop_loss
                ),
                "activation_profit_points": (
                    self.activation_profit_points
                ),
                "trailing_distance_points": (
                    self.trailing_distance_points
                ),
                "favorable_points": (
                    favorable_points
                ),
                "position": deepcopy(
                    position
                ),
            }

        updated_position = deepcopy(
            position
        )

        updated_position[
            "stop_loss"
        ] = proposed_stop

        return {
            "activated": True,
            "status": "TRAILING_ACTIVE",
            "reason": None,
            "direction": direction,
            "previous_stop_loss": (
                stop_loss
            ),
            "new_stop_loss": (
                proposed_stop
            ),
            "activation_profit_points": (
                self.activation_profit_points
            ),
            "trailing_distance_points": (
                self.trailing_distance_points
            ),
            "favorable_points": (
                favorable_points
            ),
            "position": updated_position,
        }
