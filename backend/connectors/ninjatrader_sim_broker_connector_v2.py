"""Read-only NinjaTrader SIM broker boundary.

R48G deliberately exposes BrokerConnectorV2 compatibility without
granting native mutation authority.

Allowed:
- connect / disconnect
- health
- external account evidence
- external positions
- external orders
- external fills

Forbidden in this revision:
- submit
- modify
- cancel
- partial close
- full close
"""

from __future__ import annotations

from copy import deepcopy
from typing import Callable

from backend.connectors.broker_connector_v2 import (
    BrokerConnectorV2,
)


class NinjaTraderSimBrokerConnectorV2(
    BrokerConnectorV2
):
    """Fail-closed SIM connector over a read-only native transport."""

    def __init__(
        self,
        *,
        transport,
        binding_probe: Callable[[], dict[str, object]],
        ack_authority_probe: Callable[[], dict[str, object]] | None = None,
        mutation_authority_probe: Callable[[], dict[str, object]] | None = None,
    ) -> None:
        if transport is None:
            raise TypeError(
                "transport is required."
            )

        if not callable(binding_probe):
            raise TypeError(
                "binding_probe must be callable."
            )

        if (
            ack_authority_probe is not None
            and not callable(ack_authority_probe)
        ):
            raise TypeError(
                "ack_authority_probe must be callable."
            )

        if (
            mutation_authority_probe is not None
            and not callable(mutation_authority_probe)
        ):
            raise TypeError(
                "mutation_authority_probe must be callable."
            )

        self.transport = transport
        self.binding_probe = binding_probe
        self.ack_authority_probe = ack_authority_probe
        self.mutation_authority_probe = mutation_authority_probe
        self._connected = False

    @property
    def broker_name(self) -> str:
        return "NINJATRADER_SIM"

    @property
    def execution_mode(self) -> str:
        return "SIM"

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _binding_state(
        self,
    ) -> dict[str, object]:
        state = self.binding_probe()

        if type(state) is not dict:
            raise RuntimeError(
                "SIM binding is not eligible."
            )

        if (
            state.get("future_sim_eligible") is not True
            or state.get("sim_runtime_revalidation")
            != "PASS"
            or state.get("sim_execution_authority")
            != "DISABLED"
            or state.get("external_order_authority")
            is not False
        ):
            raise RuntimeError(
                "SIM binding is not eligible."
            )

        return deepcopy(state)

    def _ack_authority_state(
        self,
    ) -> dict[str, object]:
        # The native SIM binding itself remains execution-disabled.
        # R48H uses a separate, explicitly injected ACK-only capability.
        if self.ack_authority_probe is None:
            raise RuntimeError(
                "SIM execution authority is disabled."
            )

        state = self.ack_authority_probe()

        if (
            type(state) is not dict
            or state.get("ack_submit_enabled") is not True
            or state.get("scope") != "SIM_ACK_TEST_ONLY"
        ):
            raise RuntimeError(
                "SIM execution authority is disabled."
            )

        return deepcopy(state)

    def _mutation_authority_state(
        self,
    ) -> dict[str, object]:
        # Separate test-only native mutation capability.
        # The canonical SIM binding remains execution-disabled.
        if self.mutation_authority_probe is None:
            raise RuntimeError(
                "SIM execution authority is disabled."
            )

        state = self.mutation_authority_probe()

        if (
            type(state) is not dict
            or state.get("native_mutation_enabled")
            is not True
            or state.get("scope")
            != "SIM_MUTATION_TEST_ONLY"
        ):
            raise RuntimeError(
                "SIM execution authority is disabled."
            )

        return deepcopy(state)

    def _require_connection(self) -> None:
        if not self._connected:
            raise RuntimeError(
                "SIM broker connector is not connected."
            )

    @staticmethod
    def _authority_projection() -> dict[str, object]:
        return {
            "execution_mode": "SIM",
            "sim_execution_authority": "DISABLED",
            "external_order_authority": False,
        }

    def _require_mutation_disabled(self) -> None:
        # Revalidate before refusing as well. A revoked binding must never
        # be transformed into any native mutation attempt.
        self._binding_state()

        raise RuntimeError(
            "SIM execution authority is disabled."
        )

    def connect(
        self,
    ) -> dict[str, object]:
        self._binding_state()

        result = self.transport.connect()

        if (
            type(result) is not dict
            or result.get("connected") is not True
        ):
            self._connected = False
            raise RuntimeError(
                "Native SIM transport did not connect."
            )

        self._connected = True

        return {
            **deepcopy(result),
            "broker": self.broker_name,
            **self._authority_projection(),
        }

    def disconnect(
        self,
    ) -> dict[str, object]:
        if not self._connected:
            return {
                "connected": False,
                "status": "ALREADY_DISCONNECTED",
                "broker": self.broker_name,
                **self._authority_projection(),
            }

        result = self.transport.disconnect()

        if type(result) is not dict:
            self._connected = False
            raise RuntimeError(
                "Native SIM transport disconnect failed."
            )

        self._connected = False

        return {
            **deepcopy(result),
            "connected": False,
            "broker": self.broker_name,
            **self._authority_projection(),
        }

    def health_check(
        self,
    ) -> dict[str, object]:
        binding = self._binding_state()

        if not self._connected:
            return {
                "healthy": False,
                "connected": False,
                "status": "DISCONNECTED",
                "broker": self.broker_name,
                **self._authority_projection(),
            }

        native = self.transport.health_check()

        if type(native) is not dict:
            raise RuntimeError(
                "Native SIM health evidence invalid."
            )

        healthy = (
            native.get("healthy") is True
            and native.get("connected") is True
            and binding.get("future_sim_eligible")
            is True
        )

        return {
            **deepcopy(native),
            "healthy": healthy,
            "connected": self._connected,
            "broker": self.broker_name,
            **self._authority_projection(),
        }

    def get_account(
        self,
    ) -> dict[str, object]:
        self._require_connection()
        self._binding_state()

        value = self.transport.get_account()

        if type(value) is not dict:
            raise RuntimeError(
                "Native SIM account evidence invalid."
            )

        return deepcopy(value)

    def get_positions(
        self,
    ) -> list[dict[str, object]]:
        self._require_connection()
        self._binding_state()

        value = self.transport.get_positions()

        if type(value) is not list or any(
            type(row) is not dict
            for row in value
        ):
            raise RuntimeError(
                "Native SIM positions evidence invalid."
            )

        return deepcopy(value)

    def get_orders(
        self,
    ) -> list[dict[str, object]]:
        self._require_connection()
        self._binding_state()

        value = self.transport.get_orders()

        if type(value) is not list or any(
            type(row) is not dict
            for row in value
        ):
            raise RuntimeError(
                "Native SIM orders evidence invalid."
            )

        return deepcopy(value)

    def get_fills(
        self,
    ) -> list[dict[str, object]]:
        self._require_connection()
        self._binding_state()

        value = self.transport.get_fills()

        if type(value) is not list or any(
            type(row) is not dict
            for row in value
        ):
            raise RuntimeError(
                "Native SIM fills evidence invalid."
            )

        return deepcopy(value)

    def submit_order(
        self,
        *,
        prepared_order: dict[str, object],
        client_order_id: str | None = None,
    ) -> dict[str, object]:
        self._require_connection()

        # Identity/runtime eligibility remains the R48G fail-closed contract.
        self._binding_state()

        # Separate ACK-only capability. This does not promote the binding
        # projection to execution authority.
        self._ack_authority_state()

        if type(prepared_order) is not dict:
            raise TypeError(
                "prepared_order must be a dict."
            )

        if (
            type(client_order_id) is not str
            or not client_order_id.strip()
        ):
            raise ValueError(
                "client_order_id is required."
            )

        normalized_client_order_id = (
            client_order_id.strip()
        )

        # Native evidence is authoritative for idempotency.
        # Never rely on a local client-order cache for SIM.
        native_orders = self.get_orders()

        matches = [
            deepcopy(order)
            for order in native_orders
            if order.get("client_order_id")
            == normalized_client_order_id
        ]

        if len(matches) > 1:
            raise RuntimeError(
                "ambiguous native client_order_id."
            )

        if len(matches) == 1:
            existing = matches[0]

            self._validate_ack(
                existing,
                client_order_id=(
                    normalized_client_order_id
                ),
            )

            existing["idempotent_replay"] = True
            return existing

        native = self.transport.submit_order(
            prepared_order=deepcopy(
                prepared_order
            ),
            client_order_id=(
                normalized_client_order_id
            ),
        )

        result = self._validate_ack(
            native,
            client_order_id=(
                normalized_client_order_id
            ),
        )

        result["idempotent_replay"] = False
        return result

    @staticmethod
    def _validate_ack(
        native,
        *,
        client_order_id: str,
    ) -> dict[str, object]:
        if type(native) is not dict:
            raise RuntimeError(
                "invalid native SIM order acknowledgement."
            )

        accepted = native.get("accepted")
        status = native.get("status")
        order_id = native.get("order_id")
        native_client_order_id = native.get(
            "client_order_id"
        )

        if (
            type(accepted) is not bool
            or type(status) is not str
            or status not in {
                "ACKNOWLEDGED",
                "REJECTED",
            }
            or type(order_id) is not str
            or not order_id.strip()
            or native_client_order_id
            != client_order_id
        ):
            raise RuntimeError(
                "invalid native SIM order acknowledgement."
            )

        if (
            status == "ACKNOWLEDGED"
            and accepted is not True
        ):
            raise RuntimeError(
                "invalid native SIM order acknowledgement."
            )

        if (
            status == "REJECTED"
            and accepted is not False
        ):
            raise RuntimeError(
                "invalid native SIM order acknowledgement."
            )

        # R48H is ACK only. It may never synthesize or admit fill/position
        # evidence through the submit acknowledgement boundary.
        forbidden = {
            "fill_id",
            "filled_price",
            "position_id",
            "broker_position_id",
        }

        if forbidden & set(native):
            raise RuntimeError(
                "invalid native SIM order acknowledgement."
            )

        return deepcopy(native)

    def reconcile_order(
        self,
        *,
        client_order_id: str,
    ) -> dict[str, object]:
        self._require_connection()
        self._binding_state()

        if (
            type(client_order_id) is not str
            or not client_order_id.strip()
        ):
            raise ValueError(
                "client_order_id is required."
            )

        normalized_client_order_id = (
            client_order_id.strip()
        )

        orders = self.get_orders()
        fills = self.get_fills()
        positions = self.get_positions()

        matches = [
            deepcopy(order)
            for order in orders
            if order.get("client_order_id")
            == normalized_client_order_id
        ]

        if len(matches) > 1:
            raise RuntimeError(
                "ambiguous native client_order_id."
            )

        if not matches:
            return {
                "resolved": False,
                "client_order_id":
                    normalized_client_order_id,
                "status": "NOT_FOUND",
                "order": None,
                "fills": [],
                "position": None,
                "fill_confirmed": False,
                "position_confirmed": False,
            }

        order = matches[0]

        order_id = order.get("order_id")
        status = order.get("status")
        accepted = order.get("accepted")

        if (
            type(order_id) is not str
            or not order_id.strip()
            or type(status) is not str
            or status not in {
                "ACKNOWLEDGED",
                "WORKING",
                "PARTIALLY_FILLED",
                "FILLED",
                "REJECTED",
                "CANCELLED",
            }
            or type(accepted) is not bool
        ):
            raise RuntimeError(
                "invalid native SIM order state."
            )

        if (
            status in {
                "REJECTED",
                "CANCELLED",
            }
            and accepted is not False
        ):
            raise RuntimeError(
                "invalid native SIM order state."
            )

        if (
            status not in {
                "REJECTED",
                "CANCELLED",
            }
            and accepted is not True
        ):
            raise RuntimeError(
                "invalid native SIM order state."
            )

        matching_fills = [
            deepcopy(fill)
            for fill in fills
            if fill.get("order_id") == order_id
        ]

        if (
            status == "FILLED"
            and not matching_fills
        ):
            raise RuntimeError(
                "FILLED order lacks native fill evidence."
            )

        matching_positions = [
            deepcopy(position)
            for position in positions
            if position.get("order_id") == order_id
        ]

        if len(matching_positions) > 1:
            raise RuntimeError(
                "ambiguous native position evidence."
            )

        position = (
            matching_positions[0]
            if matching_positions
            else None
        )

        return {
            "resolved": True,
            "client_order_id":
                normalized_client_order_id,
            "status": status,
            "order": deepcopy(order),
            "fills": deepcopy(
                matching_fills
            ),
            "position": deepcopy(
                position
            ),
            "fill_confirmed": bool(
                matching_fills
            ),
            "position_confirmed": (
                position is not None
            ),
        }

    def _unique_native_order(
        self,
        *,
        order_id: str,
    ) -> dict[str, object]:
        if (
            type(order_id) is not str
            or not order_id.strip()
        ):
            raise ValueError(
                "order_id is required."
            )

        normalized = order_id.strip()

        matches = [
            deepcopy(row)
            for row in self.get_orders()
            if row.get("order_id") == normalized
        ]

        if not matches:
            raise RuntimeError(
                "native order not found."
            )

        if len(matches) > 1:
            raise RuntimeError(
                "ambiguous native order identity."
            )

        return matches[0]

    def _unique_native_position(
        self,
        *,
        position_id: str,
    ) -> dict[str, object]:
        if (
            type(position_id) is not str
            or not position_id.strip()
        ):
            raise ValueError(
                "position_id is required."
            )

        normalized = position_id.strip()

        matches = [
            deepcopy(row)
            for row in self.get_positions()
            if row.get("position_id") == normalized
        ]

        if not matches:
            raise RuntimeError(
                "native position not found."
            )

        if len(matches) > 1:
            raise RuntimeError(
                "ambiguous native position identity."
            )

        return matches[0]

    @staticmethod
    def _validate_modify_ack(
        native,
        *,
        order_id: str,
    ) -> dict[str, object]:
        if (
            type(native) is not dict
            or native.get("modified") is not True
            or native.get("status") != "MODIFIED"
            or native.get("order_id") != order_id
        ):
            raise RuntimeError(
                "invalid native SIM mutation acknowledgement."
            )

        return deepcopy(native)

    @staticmethod
    def _validate_cancel_ack(
        native,
        *,
        order_id: str,
    ) -> dict[str, object]:
        if (
            type(native) is not dict
            or native.get("cancelled") is not True
            or native.get("status") != "CANCELLED"
            or native.get("order_id") != order_id
        ):
            raise RuntimeError(
                "invalid native SIM mutation acknowledgement."
            )

        return deepcopy(native)

    @staticmethod
    def _validate_close_ack(
        native,
        *,
        position_id: str,
    ) -> dict[str, object]:
        if (
            type(native) is not dict
            or native.get("closed") is not True
            or native.get("status")
            != "CLOSE_ACKNOWLEDGED"
            or native.get("position_id")
            != position_id
        ):
            raise RuntimeError(
                "invalid native SIM mutation acknowledgement."
            )

        return deepcopy(native)

    def modify_order(
        self,
        *,
        order_id: str,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        limit_price: float | None = None,
    ) -> dict[str, object]:
        self._require_connection()
        self._binding_state()
        self._mutation_authority_state()

        order = self._unique_native_order(
            order_id=order_id,
        )

        normalized_order_id = order_id.strip()

        status = str(
            order.get("status", "")
        ).strip().upper()

        if status not in {
            "ACKNOWLEDGED",
            "WORKING",
            "PARTIALLY_FILLED",
        }:
            raise RuntimeError(
                "native order is not modifiable."
            )

        requested = {
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "limit_price": limit_price,
        }

        changes = {
            key: value
            for key, value in requested.items()
            if value is not None
        }

        if not changes:
            raise ValueError(
                "at least one modification is required."
            )

        if all(
            order.get(key) == value
            for key, value in changes.items()
        ):
            return {
                "modified": True,
                "status": "ALREADY_MODIFIED",
                "order_id": normalized_order_id,
                "idempotent_replay": True,
                "order": deepcopy(order),
            }

        native = self.transport.modify_order(
            order_id=normalized_order_id,
            stop_loss=stop_loss,
            take_profit=take_profit,
            limit_price=limit_price,
        )

        result = self._validate_modify_ack(
            native,
            order_id=normalized_order_id,
        )

        result["idempotent_replay"] = False
        return result

    def cancel_order(
        self,
        *,
        order_id: str,
    ) -> dict[str, object]:
        self._require_connection()
        self._binding_state()
        self._mutation_authority_state()

        order = self._unique_native_order(
            order_id=order_id,
        )

        normalized_order_id = order_id.strip()

        status = str(
            order.get("status", "")
        ).strip().upper()

        if status == "CANCELLED":
            return {
                "cancelled": True,
                "status": "ALREADY_CANCELLED",
                "order_id": normalized_order_id,
                "idempotent_replay": True,
                "order": deepcopy(order),
            }

        if status not in {
            "ACKNOWLEDGED",
            "WORKING",
            "PARTIALLY_FILLED",
        }:
            raise RuntimeError(
                "native order is not cancellable."
            )

        native = self.transport.cancel_order(
            order_id=normalized_order_id,
        )

        result = self._validate_cancel_ack(
            native,
            order_id=normalized_order_id,
        )

        result["idempotent_replay"] = False
        return result

    def close_partial(
        self,
        *,
        position_id: str,
        quantity: float,
        current_price: float,
        reason: str,
    ) -> dict[str, object]:
        self._require_connection()
        self._binding_state()
        self._mutation_authority_state()

        # BrokerConnectorV2 currently has no durable client-operation
        # identity for partial closes. Never risk duplicate reduction.
        raise RuntimeError(
            "partial close durable identity is required."
        )

    def close_position(
        self,
        *,
        position_id: str,
        current_price: float,
        reason: str,
    ) -> dict[str, object]:
        self._require_connection()
        self._binding_state()
        self._mutation_authority_state()

        position = self._unique_native_position(
            position_id=position_id,
        )

        normalized_position_id = (
            position_id.strip()
        )

        status = str(
            position.get("status", "")
        ).strip().upper()

        if status == "CLOSED":
            return {
                "closed": True,
                "status": "ALREADY_CLOSED",
                "position_id":
                    normalized_position_id,
                "idempotent_replay": True,
                "position": deepcopy(position),
            }

        if status != "OPEN":
            raise RuntimeError(
                "native position is not closable."
            )

        if (
            type(current_price) not in (
                int,
                float,
            )
            or float(current_price) <= 0
        ):
            raise ValueError(
                "current_price must be positive."
            )

        if (
            type(reason) is not str
            or not reason.strip()
        ):
            raise ValueError(
                "reason is required."
            )

        native = self.transport.close_position(
            position_id=normalized_position_id,
            current_price=float(current_price),
            reason=reason.strip(),
        )

        result = self._validate_close_ack(
            native,
            position_id=(
                normalized_position_id
            ),
        )

        result["idempotent_replay"] = False
        return result
