from __future__ import annotations

from backend.account.account_state_manager_v2 import (
    AccountStateManagerV2,
)

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
        account_state_manager_v2:
        AccountStateManagerV2
        | None = None,
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

        if (
            account_state_manager_v2
            is not None
            and not isinstance(
                account_state_manager_v2,
                AccountStateManagerV2,
            )
        ):
            raise TypeError(
                "account_state_manager_v2 debe ser "
                "AccountStateManagerV2."
            )

        self.account_state_manager_v2 = (
            account_state_manager_v2
        )


        self._open_positions = {}

        self._closed_positions = []

    def _sync_account_state(
        self,
    ) -> dict[str, object] | None:
        if (
            self.account_state_manager_v2
            is None
        ):
            return None

        summary = {
            "starting_balance": (
                self.starting_balance
            ),
            "open_positions": len(
                self._open_positions
            ),
            "closed_positions": len(
                self._closed_positions
            ),
            "total_realized_pnl": (
                self.get_total_realized_pnl()
            ),
            "total_unrealized_pnl": (
                self.get_total_unrealized_pnl()
            ),
            "total_pnl": (
                self.get_total_pnl()
            ),
            "account_equity": (
                self.get_account_equity()
            ),
        }

        result = (
            self.account_state_manager_v2
            .update_from_portfolio(
                portfolio_summary=summary,
            )
        )

        return result["state"]

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

        account_state = (
            self._sync_account_state()
        )

        return {
            "added": True,
            "status": "ADDED",
            "position_id": position_id,
            "account_state": account_state,
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

        account_state = (
            self._sync_account_state()
        )

        return {
            "updated": True,
            "position": deepcopy(
                self._open_positions[
                    position_id
                ]
            ),
            "account_state": account_state,
        }

    def reduce_position(
        self,
        *,
        position_id: str,
        remaining_quantity: float,
        current_price: float,
        realized_pnl: float,
    ) -> dict[str, object]:
        if position_id not in self._open_positions:
            raise KeyError(
                "position_id"
            )

        normalized_remaining = float(
            remaining_quantity
        )

        normalized_price = float(
            current_price
        )

        normalized_realized = float(
            realized_pnl
        )

        if normalized_remaining <= 0:
            raise ValueError(
                "remaining_quantity debe ser "
                "mayor que cero."
            )

        if normalized_price <= 0:
            raise ValueError(
                "current_price debe ser "
                "mayor que cero."
            )

        position = deepcopy(
            self._open_positions[
                position_id
            ]
        )

        current_quantity = float(
            position.get(
                "quantity",
                0.0,
            )
        )

        if (
            current_quantity <= 0
            or normalized_remaining
            >= current_quantity
        ):
            raise ValueError(
                "remaining_quantity debe ser menor "
                "que la cantidad abierta."
            )

        position[
            "quantity"
        ] = normalized_remaining

        position[
            "current_price"
        ] = normalized_price

        position[
            "realized_pnl"
        ] = round(
            float(
                position.get(
                    "realized_pnl",
                    0.0,
                )
                or 0.0
            )
            + normalized_realized,
            10,
        )

        position[
            "partial_taken"
        ] = True

        self._open_positions[
            position_id
        ] = position

        account_state = (
            self._sync_account_state()
        )

        return {
            "reduced": True,
            "status": "PARTIALLY_CLOSED",
            "position_id": position_id,
            "position": deepcopy(
                position
            ),
            "account_state": account_state,
        }

    def close_position(
        self,
        *,
        position_id: str,
        exit_price: float,
        realized_pnl: float | None = None,
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

        previous_realized_pnl = float(
            position.get(
                "realized_pnl",
                0.0,
            )
            or 0.0
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

        previous_realized = float(
            position.get(
                "realized_pnl",
                0.0,
            )
            or 0.0
        )

        if direction == "LONG":
            remaining_pnl = (
                exit_price - entry
            ) * quantity * point_value
        else:
            remaining_pnl = (
                entry - exit_price
            ) * quantity * point_value


        if "total_pnl" in position:

            pnl = float(
                position.get(
                    "total_pnl",
                    0.0,
                )
                or 0.0
            )

        elif realized_pnl is not None:

            pnl = float(
                realized_pnl
            )

        else:

            pnl = round(
                previous_realized + remaining_pnl,
                10,
            )

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

        account_state = (
            self._sync_account_state()
        )

        return {
            "closed": True,
            "status": "CLOSED",
            "position": deepcopy(
                position
            ),
            "account_state": account_state,
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
            "account_state": (
                self.account_state_manager_v2
                .get_state()
                if self.account_state_manager_v2
                is not None
                else None
            ),
        }
