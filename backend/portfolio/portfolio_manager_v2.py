from __future__ import annotations

from copy import deepcopy


class PortfolioManagerV2:

    VALID_DIRECTIONS = {
        "LONG",
        "SHORT",
    }

    def __init__(
        self,
        *,
        starting_balance: float,
    ) -> None:

        starting_balance = float(
            starting_balance
        )

        if starting_balance <= 0:
            raise ValueError(
                "starting_balance debe ser mayor que cero."
            )

        self.starting_balance = (
            starting_balance
        )

        self._open_positions = {}

        self._closed_positions = []

    def add_position(
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

        position_id = position.get(
            "position_id"
        )

        if not position_id:
            raise ValueError(
                "position_id es obligatorio."
            )

        if position_id in self._open_positions:
            raise ValueError(
                "position_id duplicado."
            )

        self._open_positions[
            position_id
        ] = deepcopy(position)

        return {
            "added": True,
            "status": "ADDED",
            "position_id": position_id,
        }

    def update_position(
        self,
        *,
        position_id: str,
        updates: dict[str, object],
    ) -> dict[str, object]:

        if position_id not in self._open_positions:
            raise KeyError(
                "position_id"
            )

        self._open_positions[
            position_id
        ].update(updates)

        return {
            "updated": True,
            "position": deepcopy(
                self._open_positions[
                    position_id
                ]
            ),
        }

    def close_position(
        self,
        *,
        position_id: str,
        exit_price: float,
    ) -> dict[str, object]:

        if position_id not in self._open_positions:
            raise KeyError(
                "position_id"
            )

        exit_price = float(exit_price)

        if exit_price <= 0:
            raise ValueError(
                "exit_price debe ser mayor que cero."
            )

        position = self._open_positions.pop(
            position_id
        )

        quantity = float(
            position["quantity"]
        )

        entry = float(
            position["entry_price"]
        )

        point_value = float(
            position["point_value"]
        )

        direction = str(
            position["direction"]
        ).upper()

        if direction == "LONG":
            pnl = (
                exit_price - entry
            ) * quantity * point_value
        else:
            pnl = (
                entry - exit_price
            ) * quantity * point_value

        position = deepcopy(position)

        position["status"] = "CLOSED"
        position["exit_price"] = exit_price
        position["realized_pnl"] = round(
            pnl,
            10,
        )

        self._closed_positions.append(
            position
        )

        return {
            "closed": True,
            "status": "CLOSED",
            "position": deepcopy(
                position
            ),
        }

    def get_open_positions(self):
        return deepcopy(
            list(
                self._open_positions.values()
            )
        )

    def get_closed_positions(self):
        return deepcopy(
            self._closed_positions
        )

    def get_total_realized_pnl(self):

        return round(
            sum(
                float(
                    p.get(
                        "realized_pnl",
                        0.0,
                    )
                )
                for p in self._closed_positions
            ),
            10,
        )

    def get_total_unrealized_pnl(self):

        total = 0.0

        for p in self._open_positions.values():

            qty = float(
                p["quantity"]
            )

            entry = float(
                p["entry_price"]
            )

            current = float(
                p["current_price"]
            )

            point_value = float(
                p["point_value"]
            )

            direction = str(
                p["direction"]
            ).upper()

            if direction == "LONG":
                total += (
                    current - entry
                ) * qty * point_value
            else:
                total += (
                    entry - current
                ) * qty * point_value

        return round(
            total,
            10,
        )

    def get_total_pnl(self):

        return (
            self.get_total_realized_pnl()
            + self.get_total_unrealized_pnl()
        )

    def get_account_equity(self):

        return round(
            self.starting_balance
            + self.get_total_pnl(),
            10,
        )

    def get_available_balance(self):

        return round(
            self.starting_balance
            + self.get_total_realized_pnl(),
            10,
        )

    def get_summary(self):

        return {
            "starting_balance":
                self.starting_balance,
            "open_positions":
                len(
                    self._open_positions
                ),
            "closed_positions":
                len(
                    self._closed_positions
                ),
            "total_realized_pnl":
                self.get_total_realized_pnl(),
            "total_unrealized_pnl":
                self.get_total_unrealized_pnl(),
            "total_pnl":
                self.get_total_pnl(),
            "account_equity":
                self.get_account_equity(),
        }
