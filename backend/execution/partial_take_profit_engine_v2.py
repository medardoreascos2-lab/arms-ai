from __future__ import annotations

from copy import deepcopy


class PartialTakeProfitEngineV2:
    """
    Ejecuta una toma parcial de beneficios
    cuando la posición alcanza la ganancia
    configurada.
    """

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        trigger_profit_points: float,
        close_fraction: float,
    ) -> None:
        normalized_trigger = float(
            trigger_profit_points
        )

        normalized_fraction = float(
            close_fraction
        )

        if normalized_trigger <= 0:
            raise ValueError(
                "trigger_profit_points debe ser "
                "mayor que cero."
            )

        if not (
            0.0
            < normalized_fraction
            < 1.0
        ):
            raise ValueError(
                "close_fraction debe estar "
                "entre 0 y 1."
            )

        self.trigger_profit_points = (
            normalized_trigger
        )

        self.close_fraction = (
            normalized_fraction
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
                "executed": False,
                "status": "INACTIVE",
                "reason": "position_not_open",
                "position": deepcopy(
                    position
                ),
            }

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

        quantity_value = position.get(
            "quantity"
        )

        if quantity_value is None:
            raise ValueError(
                "quantity es obligatorio."
            )

        quantity = float(
            quantity_value
        )

        if quantity <= 0:
            raise ValueError(
                "quantity debe ser "
                "mayor que cero."
            )

        if bool(
            position.get(
                "partial_taken",
                False,
            )
        ):
            return {
                "executed": False,
                "status": "ALREADY_EXECUTED",
                "reason": (
                    "partial_already_taken"
                ),
                "closed_quantity": 0.0,
                "remaining_quantity": (
                    quantity
                ),
                "position": deepcopy(
                    position
                ),
            }

        if direction == "LONG":
            favorable_points = round(
                normalized_current_price
                - entry_price,
                10,
            )
        else:
            favorable_points = round(
                entry_price
                - normalized_current_price,
                10,
            )

        if (
            favorable_points
            < self.trigger_profit_points
        ):
            return {
                "executed": False,
                "status": "WAITING",
                "reason": (
                    "trigger_not_reached"
                ),
                "closed_quantity": 0.0,
                "remaining_quantity": (
                    quantity
                ),
                "trigger_profit_points": (
                    self.trigger_profit_points
                ),
                "favorable_points": (
                    favorable_points
                ),
                "position": deepcopy(
                    position
                ),
            }

        closed_quantity = round(
            quantity
            * self.close_fraction,
            10,
        )

        remaining_quantity = round(
            quantity
            - closed_quantity,
            10,
        )

        if closed_quantity <= 0:
            raise ValueError(
                "closed_quantity calculada "
                "debe ser mayor que cero."
            )

        if remaining_quantity <= 0:
            raise ValueError(
                "remaining_quantity calculada "
                "debe ser mayor que cero."
            )

        updated_position = deepcopy(
            position
        )

        updated_position[
            "quantity"
        ] = remaining_quantity

        updated_position[
            "partial_taken"
        ] = True

        updated_position[
            "partial_exit_price"
        ] = normalized_current_price

        updated_position[
            "partial_closed_quantity"
        ] = closed_quantity

        return {
            "executed": True,
            "status": "PARTIAL_TAKEN",
            "reason": None,
            "direction": direction,
            "closed_quantity": (
                closed_quantity
            ),
            "remaining_quantity": (
                remaining_quantity
            ),
            "close_fraction": (
                self.close_fraction
            ),
            "trigger_profit_points": (
                self.trigger_profit_points
            ),
            "favorable_points": (
                favorable_points
            ),
            "execution_price": (
                normalized_current_price
            ),
            "position": updated_position,
        }
