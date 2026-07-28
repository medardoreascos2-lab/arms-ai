from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone
from uuid import uuid4

from backend.connectors.broker_connector_v2 import (
    BrokerConnectorV2,
)
from backend.execution.paper_execution_engine_v2 import (
    PaperExecutionEngineV2,
)


class PaperBrokerConnectorV2(
    BrokerConnectorV2
):
    """
    Adaptador PAPER compatible con BrokerConnectorV2.

    Reutiliza PaperExecutionEngineV2 y mantiene un registro
    en memoria de órdenes, fills y posiciones simuladas.
    """

    VALID_FINAL_ORDER_STATUSES = {
        "FILLED",
        "CANCELLED",
        "REJECTED",
    }

    def __init__(
        self,
        *,
        execution_engine:
        PaperExecutionEngineV2,
        account_id: str = "ARMS-PAPER-001",
        starting_balance: float = 17000.0,
    ) -> None:
        if not isinstance(
            execution_engine,
            PaperExecutionEngineV2,
        ):
            raise TypeError(
                "execution_engine debe ser "
                "PaperExecutionEngineV2."
            )

        normalized_account_id = (
            str(account_id)
            .strip()
            .upper()
        )

        if not normalized_account_id:
            raise ValueError(
                "account_id es obligatorio."
            )

        normalized_balance = float(
            starting_balance
        )

        if normalized_balance <= 0:
            raise ValueError(
                "starting_balance debe ser "
                "mayor que cero."
            )

        self.execution_engine = (
            execution_engine
        )
        self.account_id = (
            normalized_account_id
        )
        self.starting_balance = (
            normalized_balance
        )
        self._connected = False

        self._orders: dict[
            str,
            dict[str, object],
        ] = {}

        self._fills: list[
            dict[str, object]
        ] = []

        self._positions: dict[
            str,
            dict[str, object],
        ] = {}

        self._client_order_index: dict[
            str,
            str,
        ] = {}

    @property
    def broker_name(self) -> str:
        return "ARMS_PAPER"

    @property
    def execution_mode(self) -> str:
        return "PAPER"

    @property
    def is_connected(self) -> bool:
        return self._connected

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

    @staticmethod
    def _normalize_identifier(
        value: object,
        *,
        field_name: str,
    ) -> str:
        normalized = (
            str(value)
            .strip()
        )

        if not normalized:
            raise ValueError(
                f"{field_name} es obligatorio."
            )

        return normalized

    def _require_connection(self) -> None:
        if not self._connected:
            raise RuntimeError(
                "El broker connector no está "
                "conectado."
            )

    def connect(self) -> dict[str, object]:
        already_connected = (
            self._connected
        )

        self._connected = True

        return {
            "connected": True,
            "status": (
                "ALREADY_CONNECTED"
                if already_connected
                else "CONNECTED"
            ),
            "broker": self.broker_name,
            "execution_mode": (
                self.execution_mode
            ),
            "account_id": self.account_id,
            "timestamp": self._utc_now(),
        }

    def disconnect(self) -> dict[str, object]:
        was_connected = self._connected
        self._connected = False

        return {
            "connected": False,
            "status": (
                "DISCONNECTED"
                if was_connected
                else "ALREADY_DISCONNECTED"
            ),
            "broker": self.broker_name,
            "execution_mode": (
                self.execution_mode
            ),
            "account_id": self.account_id,
            "timestamp": self._utc_now(),
        }

    def health_check(self) -> dict[str, object]:
        return {
            "healthy": self._connected,
            "status": (
                "READY"
                if self._connected
                else "DISCONNECTED"
            ),
            "broker": self.broker_name,
            "execution_mode": (
                self.execution_mode
            ),
            "account_id": self.account_id,
            "orders": len(
                self._orders
            ),
            "fills": len(
                self._fills
            ),
            "positions": len(
                self._positions
            ),
            "timestamp": self._utc_now(),
        }

    def submit_order(
        self,
        *,
        prepared_order: dict[str, object],
        client_order_id: str | None = None,
    ) -> dict[str, object]:
        self._require_connection()

        if not isinstance(
            prepared_order,
            dict,
        ):
            raise TypeError(
                "prepared_order debe ser "
                "un dict."
            )

        normalized_client_order_id = None

        if client_order_id is not None:
            normalized_client_order_id = (
                self._normalize_identifier(
                    client_order_id,
                    field_name=(
                        "client_order_id"
                    ),
                )
            )

            existing_order_id = (
                self._client_order_index.get(
                    normalized_client_order_id
                )
            )

            if existing_order_id is not None:
                existing = deepcopy(
                    self._orders[
                        existing_order_id
                    ]
                )

                existing[
                    "idempotent_replay"
                ] = True

                return existing

        execution = (
            self.execution_engine.execute(
                prepared_order=(
                    deepcopy(
                        prepared_order
                    )
                ),
            )
        )

        order_id = (
            str(
                execution.get(
                    "order_id"
                )
                or uuid4()
            )
        )

        order_record = deepcopy(
            execution
        )

        order_record.update(
            {
                "order_id": order_id,
                "broker": self.broker_name,
                "client_order_id": (
                    normalized_client_order_id
                ),
                "submitted_at": (
                    self._utc_now()
                ),
                "updated_at": (
                    self._utc_now()
                ),
                "idempotent_replay": False,
            }
        )

        self._orders[
            order_id
        ] = order_record

        if normalized_client_order_id:
            self._client_order_index[
                normalized_client_order_id
            ] = order_id

        if (
            bool(
                order_record.get(
                    "accepted",
                    False,
                )
            )
            and str(
                order_record.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
            == "FILLED"
        ):
            fill_record = {
                "fill_id": str(
                    uuid4()
                ),
                "order_id": order_id,
                "broker": self.broker_name,
                "execution_mode": (
                    self.execution_mode
                ),
                "symbol": (
                    order_record.get(
                        "symbol"
                    )
                ),
                "side": (
                    order_record.get(
                        "side"
                    )
                ),
                "quantity": (
                    order_record.get(
                        "quantity"
                    )
                ),
                "filled_price": (
                    order_record.get(
                        "filled_price"
                    )
                ),
                "filled_at": (
                    self._utc_now()
                ),
            }

            self._fills.append(
                fill_record
            )

            position_id = str(
                uuid4()
            )

            self._positions[
                position_id
            ] = {
                "position_id": position_id,
                "order_id": order_id,
                "broker": self.broker_name,
                "execution_mode": (
                    self.execution_mode
                ),
                "status": "OPEN",
                "symbol": (
                    order_record.get(
                        "symbol"
                    )
                ),
                "side": (
                    order_record.get(
                        "side"
                    )
                ),
                "quantity": (
                    order_record.get(
                        "quantity"
                    )
                ),
                "entry_price": (
                    order_record.get(
                        "filled_price"
                    )
                ),
                "current_price": (
                    order_record.get(
                        "filled_price"
                    )
                ),
                "stop_loss": (
                    order_record.get(
                        "stop_loss"
                    )
                ),
                "take_profit": (
                    order_record.get(
                        "take_profit"
                    )
                ),
                "opened_at": (
                    self._utc_now()
                ),
            }

            order_record[
                "position_id"
            ] = position_id

            self._orders[
                order_id
            ] = deepcopy(
                order_record
            )

        return deepcopy(
            order_record
        )

    def modify_order(
        self,
        *,
        order_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        limit_price: float | None = None,
    ) -> dict[str, object]:
        self._require_connection()

        normalized_order_id = (
            self._normalize_identifier(
                order_id,
                field_name="order_id",
            )
        )

        if normalized_order_id not in self._orders:
            return {
                "modified": False,
                "status": "NOT_FOUND",
                "order_id": (
                    normalized_order_id
                ),
                "reason": (
                    "order_not_found"
                ),
            }

        if (
            stop_loss is None
            and take_profit is None
            and limit_price is None
        ):
            raise ValueError(
                "Debe proporcionarse al menos "
                "un campo para modificar."
            )

        order = deepcopy(
            self._orders[
                normalized_order_id
            ]
        )

        if stop_loss is not None:
            normalized_stop = float(
                stop_loss
            )

            if normalized_stop <= 0:
                raise ValueError(
                    "stop_loss debe ser "
                    "mayor que cero."
                )

            order[
                "stop_loss"
            ] = normalized_stop

        if take_profit is not None:
            normalized_target = float(
                take_profit
            )

            if normalized_target <= 0:
                raise ValueError(
                    "take_profit debe ser "
                    "mayor que cero."
                )

            order[
                "take_profit"
            ] = normalized_target

        if limit_price is not None:
            normalized_limit = float(
                limit_price
            )

            if normalized_limit <= 0:
                raise ValueError(
                    "limit_price debe ser "
                    "mayor que cero."
                )

            order[
                "limit_price"
            ] = normalized_limit

        order[
            "updated_at"
        ] = self._utc_now()

        order[
            "modified"
        ] = True

        self._orders[
            normalized_order_id
        ] = order

        position_id = order.get(
            "position_id"
        )

        if (
            position_id is not None
            and str(position_id)
            in self._positions
        ):
            position = deepcopy(
                self._positions[
                    str(position_id)
                ]
            )

            if stop_loss is not None:
                position[
                    "stop_loss"
                ] = order[
                    "stop_loss"
                ]

            if take_profit is not None:
                position[
                    "take_profit"
                ] = order[
                    "take_profit"
                ]

            self._positions[
                str(position_id)
            ] = position

        return {
            "modified": True,
            "status": "MODIFIED",
            "order_id": (
                normalized_order_id
            ),
            "order": deepcopy(
                order
            ),
        }

    def cancel_order(
        self,
        *,
        order_id: str,
    ) -> dict[str, object]:
        self._require_connection()

        normalized_order_id = (
            self._normalize_identifier(
                order_id,
                field_name="order_id",
            )
        )

        if normalized_order_id not in self._orders:
            return {
                "cancelled": False,
                "status": "NOT_FOUND",
                "order_id": (
                    normalized_order_id
                ),
                "reason": (
                    "order_not_found"
                ),
            }

        order = deepcopy(
            self._orders[
                normalized_order_id
            ]
        )

        status = (
            str(
                order.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
        )

        if status in self.VALID_FINAL_ORDER_STATUSES:
            return {
                "cancelled": False,
                "status": (
                    "NOT_CANCELLABLE"
                ),
                "order_id": (
                    normalized_order_id
                ),
                "reason": (
                    "order_already_final"
                ),
                "order": order,
            }

        order["status"] = "CANCELLED"
        order["accepted"] = False
        order[
            "cancelled_at"
        ] = self._utc_now()
        order[
            "updated_at"
        ] = self._utc_now()

        self._orders[
            normalized_order_id
        ] = order

        return {
            "cancelled": True,
            "status": "CANCELLED",
            "order_id": (
                normalized_order_id
            ),
            "order": deepcopy(
                order
            ),
        }

    def close_position(
        self,
        *,
        position_id: str,
        current_price: float,
        reason: str,
    ) -> dict[str, object]:
        self._require_connection()

        normalized_position_id = (
            self._normalize_identifier(
                position_id,
                field_name=(
                    "position_id"
                ),
            )
        )

        normalized_price = float(
            current_price
        )

        if normalized_price <= 0:
            raise ValueError(
                "current_price debe ser "
                "mayor que cero."
            )

        normalized_reason = (
            self._normalize_identifier(
                reason,
                field_name="reason",
            )
        )

        if (
            normalized_position_id
            not in self._positions
        ):
            return {
                "closed": False,
                "status": "NOT_FOUND",
                "position_id": (
                    normalized_position_id
                ),
                "reason": (
                    "position_not_found"
                ),
            }

        position = deepcopy(
            self._positions[
                normalized_position_id
            ]
        )

        if (
            str(
                position.get(
                    "status",
                    "",
                )
            )
            .strip()
            .upper()
            != "OPEN"
        ):
            return {
                "closed": False,
                "status": (
                    "ALREADY_CLOSED"
                ),
                "position_id": (
                    normalized_position_id
                ),
                "position": position,
            }

        position[
            "status"
        ] = "CLOSED"

        position[
            "current_price"
        ] = normalized_price

        position[
            "exit_price"
        ] = normalized_price

        position[
            "close_reason"
        ] = normalized_reason

        position[
            "closed_at"
        ] = self._utc_now()

        self._positions[
            normalized_position_id
        ] = position

        return {
            "closed": True,
            "status": "CLOSED",
            "position_id": (
                normalized_position_id
            ),
            "position": deepcopy(
                position
            ),
        }

    def get_account(self) -> dict[str, object]:
        self._require_connection()

        return {
            "account_id": self.account_id,
            "broker": self.broker_name,
            "execution_mode": (
                self.execution_mode
            ),
            "status": "ACTIVE",
            "starting_balance": (
                self.starting_balance
            ),
            "balance": (
                self.starting_balance
            ),
            "equity": (
                self.starting_balance
            ),
            "currency": "USD",
            "open_positions": sum(
                1
                for position
                in self._positions.values()
                if str(
                    position.get(
                        "status",
                        "",
                    )
                )
                .strip()
                .upper()
                == "OPEN"
            ),
        }

    def get_positions(
        self,
    ) -> list[dict[str, object]]:
        self._require_connection()

        return [
            deepcopy(position)
            for position
            in self._positions.values()
        ]

    def get_orders(
        self,
    ) -> list[dict[str, object]]:
        self._require_connection()

        return [
            deepcopy(order)
            for order
            in self._orders.values()
        ]

    def get_fills(
        self,
    ) -> list[dict[str, object]]:
        self._require_connection()

        return deepcopy(
            self._fills
        )
