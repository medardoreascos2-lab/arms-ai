from __future__ import annotations

from copy import deepcopy


class BreakEvenEngineV2:

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        trigger_profit_points: float,
        offset_points: float,
    ) -> None:

        trigger_profit_points = float(
            trigger_profit_points
        )

        offset_points = float(
            offset_points
        )

        if trigger_profit_points <= 0:
            raise ValueError(
                "trigger_profit_points debe ser mayor que cero."
            )

        if offset_points < 0:
            raise ValueError(
                "offset_points no puede ser negativo."
            )

        self.trigger_profit_points = (
            trigger_profit_points
        )

        self.offset_points = (
            offset_points
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

        current_price = float(
            current_price
        )

        if current_price <= 0:
            raise ValueError(
                "current_price debe ser mayor que cero."
            )

        direction = str(
            position.get(
                "direction",
                "",
            )
        ).upper()

        if direction not in self.VALID_DIRECTIONS:
            raise ValueError(
                "direction inválida."
            )

        if (
            str(
                position.get(
                    "status",
                    "",
                )
            ).upper()
            != "OPEN"
        ):
            return {
                "activated": False,
                "status": "INACTIVE",
                "reason": "position_not_open",
            }

        entry_price = position.get(
            "entry_price"
        )

        stop_loss = position.get(
            "stop_loss"
        )

        if (
            entry_price is None
            or float(entry_price) <= 0
        ):
            raise ValueError(
                "entry_price inválido."
            )

        if stop_loss is None:
            raise ValueError(
                "stop_loss inválido."
            )

        entry_price = float(
            entry_price
        )

        stop_loss = float(
            stop_loss
        )

        if direction == "LONG":

            favorable_points = (
                current_price
                - entry_price
            )

            new_stop = (
                entry_price
                + self.offset_points
            )

            if stop_loss >= new_stop:
                return {
                    "activated": False,
                    "status": "ALREADY_PROTECTED",
                    "reason": "stop_already_at_or_beyond_break_even",
                    "position": deepcopy(
                        position
                    ),
                }

        else:

            favorable_points = (
                entry_price
                - current_price
            )

            new_stop = (
                entry_price
                - self.offset_points
            )

            if stop_loss <= new_stop:
                return {
                    "activated": False,
                    "status": "ALREADY_PROTECTED",
                    "reason": "stop_already_at_or_beyond_break_even",
                    "position": deepcopy(
                        position
                    ),
                }

        if (
            favorable_points
            < self.trigger_profit_points
        ):
            return {
                "activated": False,
                "status": "WAITING",
                "reason": "trigger_not_reached",
                "new_stop_loss": stop_loss,
                "position": deepcopy(
                    position
                ),
            }

        updated = deepcopy(
            position
        )

        updated["stop_loss"] = new_stop

        return {
            "activated": True,
            "status": "BREAK_EVEN_ACTIVE",
            "direction": direction,
            "previous_stop_loss": stop_loss,
            "new_stop_loss": new_stop,
            "trigger_profit_points": (
                self.trigger_profit_points
            ),
            "favorable_points": favorable_points,
            "position": updated,
        }
