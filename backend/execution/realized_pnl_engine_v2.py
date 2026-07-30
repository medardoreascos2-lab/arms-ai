from __future__ import annotations

from copy import deepcopy


class RealizedPnLEngineV2:
    """
    Calcula el PnL realizado de un parcial,
    el PnL no realizado de la cantidad restante
    y el PnL total de la operación.
    """

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        point_value: float,
    ) -> None:
        normalized_point_value = float(
            point_value
        )

        if normalized_point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

        self.point_value = (
            normalized_point_value
        )

    def calculate(
        self,
        *,
        position: dict[str, object],
    ) -> dict[str, object]:
        if not isinstance(
            position,
            dict,
        ):
            raise TypeError(
                "position debe ser un dict."
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
                "direction debe ser LONG o SHORT."
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
                "entry_price debe ser mayor que cero."
            )

        current_price_value = position.get(
            "current_price"
        )

        if current_price_value is None:
            raise ValueError(
                "current_price es obligatorio."
            )

        current_price = float(
            current_price_value
        )

        if current_price <= 0:
            raise ValueError(
                "current_price debe ser mayor que cero."
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
                "quantity debe ser mayor que cero."
            )

        if not bool(
            position.get(
                "partial_taken",
                False,
            )
        ):
            return {
                "calculated": False,
                "status": "WAITING",
                "reason": "partial_not_taken",
                "position": deepcopy(
                    position
                ),
            }

        if bool(
            position.get(
                "partial_pnl_recorded",
                False,
            )
        ):
            return {
                "calculated": False,
                "status": "ALREADY_RECORDED",
                "reason": (
                    "partial_pnl_already_recorded"
                ),
                "position": deepcopy(
                    position
                ),
            }

        partial_exit_price_value = (
            position.get(
                "partial_exit_price"
            )
        )

        if partial_exit_price_value is None:
            raise ValueError(
                "partial_exit_price es obligatorio."
            )

        partial_exit_price = float(
            partial_exit_price_value
        )

        if partial_exit_price <= 0:
            raise ValueError(
                "partial_exit_price debe ser "
                "mayor que cero."
            )

        partial_closed_quantity_value = (
            position.get(
                "partial_closed_quantity"
            )
        )

        if partial_closed_quantity_value is None:
            raise ValueError(
                "partial_closed_quantity es "
                "obligatorio."
            )

        partial_closed_quantity = float(
            partial_closed_quantity_value
        )

        if partial_closed_quantity <= 0:
            raise ValueError(
                "partial_closed_quantity debe ser "
                "mayor que cero."
            )

        previous_realized_pnl = float(
            position.get(
                "realized_pnl"
            )
            or 0.0
        )

        if direction == "LONG":
            realized_points = round(
                partial_exit_price
                - entry_price,
                10,
            )

            unrealized_points = round(
                current_price
                - entry_price,
                10,
            )
        else:
            realized_points = round(
                entry_price
                - partial_exit_price,
                10,
            )

            unrealized_points = round(
                entry_price
                - current_price,
                10,
            )

        realized_pnl = round(
            realized_points
            * partial_closed_quantity
            * self.point_value,
            10,
        )

        total_realized_pnl = round(
            previous_realized_pnl
            + realized_pnl,
            10,
        )

        unrealized_pnl = round(
            unrealized_points
            * quantity
            * self.point_value,
            10,
        )

        total_pnl = round(
            total_realized_pnl
            + unrealized_pnl,
            10,
        )

        updated_position = deepcopy(
            position
        )

        updated_position[
            "realized_pnl"
        ] = total_realized_pnl

        updated_position[
            "unrealized_pnl"
        ] = unrealized_pnl

        updated_position[
            "total_pnl"
        ] = total_pnl

        updated_position[
            "partial_pnl_recorded"
        ] = True

        return {
            "calculated": True,
            "status": "CALCULATED",
            "reason": None,
            "direction": direction,
            "point_value": self.point_value,
            "realized_points": (
                realized_points
            ),
            "realized_pnl": realized_pnl,
            "previous_realized_pnl": (
                previous_realized_pnl
            ),
            "total_realized_pnl": (
                total_realized_pnl
            ),
            "unrealized_points": (
                unrealized_points
            ),
            "unrealized_pnl": (
                unrealized_pnl
            ),
            "total_pnl": total_pnl,
            "position": updated_position,
        }
