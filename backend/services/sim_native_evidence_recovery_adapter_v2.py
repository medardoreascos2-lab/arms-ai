from __future__ import annotations

from copy import deepcopy
from typing import Any


class SimNativeEvidenceRecoveryAdapterV2:
    execution_mode = "SIM"

    def __init__(
        self,
        *,
        command_id: str,
        evidence_reconciler: Any,
        evidence_reader: Any,
    ) -> None:
        if (
            type(command_id) is not str
            or not command_id.strip()
        ):
            raise TypeError(
                "command_id is required."
            )

        if evidence_reconciler is None:
            raise TypeError(
                "evidence_reconciler is required."
            )

        if evidence_reader is None:
            raise TypeError(
                "evidence_reader is required."
            )

        if not callable(
            getattr(
                evidence_reconciler,
                "reconcile",
                None,
            )
        ):
            raise TypeError(
                "evidence_reconciler must support reconcile."
            )

        if not callable(
            getattr(
                evidence_reader,
                "read_for_command",
                None,
            )
        ):
            raise TypeError(
                "evidence_reader must support read_for_command."
            )

        self.command_id = command_id.strip()
        self.evidence_reconciler = (
            evidence_reconciler
        )
        self.evidence_reader = evidence_reader

    @staticmethod
    def _base_native(
        *,
        client_order_id: str,
        status: str,
        resolved: bool,
        order,
        fills,
        fill_confirmed: bool,
    ) -> dict[str, Any]:
        return {
            "resolved": resolved,
            "client_order_id": client_order_id,
            "status": status,
            "order": deepcopy(order),
            "fills": deepcopy(fills),
            "position": None,
            "fill_confirmed": fill_confirmed,
            "position_confirmed": False,
        }

    @staticmethod
    def _execution_events(
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in events
            if event.get("event_type")
            == "EXECUTION_UPDATE"
        ]

    @staticmethod
    def _order_events(
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            event
            for event in events
            if event.get("event_type")
            == "ORDER_UPDATE"
        ]

    @staticmethod
    def _native_fills(
        execution_events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        fills = []

        for event in execution_events:
            fills.append(
                {
                    "fill_id": event["execution_id"],
                    "order_id": event["order_id"],
                    "quantity": event["quantity"],
                    "filled_price": event["price"],
                }
            )

        return fills

    @staticmethod
    def _terminal_state(
        order_events: list[dict[str, Any]],
    ) -> str | None:
        states = {
            event.get("order_state")
            for event in order_events
        }

        terminal = {
            state
            for state in states
            if state in {
                "Rejected",
                "Cancelled",
            }
        }

        if len(terminal) > 1:
            raise RuntimeError(
                "multiple terminal native states detected"
            )

        if not terminal:
            return None

        return next(iter(terminal))

    def reconcile_order(
        self,
        *,
        client_order_id: str,
    ) -> dict[str, Any]:
        if (
            type(client_order_id) is not str
            or not client_order_id.strip()
        ):
            raise ValueError(
                "client_order_id is required."
            )

        operation_id = client_order_id.strip()

        result = self.evidence_reconciler.reconcile(
            command_id=self.command_id,
            operation_id=operation_id,
            client_order_id=operation_id,
        )

        if type(result) is not dict:
            raise RuntimeError(
                "evidence reconciliation shape is invalid"
            )

        if (
            result.get("automatic_retry_allowed")
            is not False
        ):
            raise RuntimeError(
                "automatic retry is forbidden"
            )

        events = self.evidence_reader.read_for_command(
            command_id=self.command_id,
            operation_id=operation_id,
            client_order_id=operation_id,
        )

        if type(events) is not list:
            raise RuntimeError(
                "native evidence shape is invalid"
            )

        order_events = self._order_events(
            events
        )

        execution_events = (
            self._execution_events(
                events
            )
        )

        status = result.get("status")
        native_order_id = result.get(
            "native_order_id"
        )

        if status == "RECOVERY_REQUIRED":
            if events:
                raise RuntimeError(
                    "recovery-required state has native evidence"
                )

            return self._base_native(
                client_order_id=operation_id,
                status="NOT_FOUND",
                resolved=False,
                order=None,
                fills=[],
                fill_confirmed=False,
            )

        if status == "PENDING_NATIVE":
            if (
                type(native_order_id) is not str
                or not native_order_id
            ):
                raise RuntimeError(
                    "pending native order id is missing"
                )

            filled_quantity = result.get(
                "filled_quantity"
            )

            if (
                type(filled_quantity) is not int
                or filled_quantity < 0
            ):
                raise RuntimeError(
                    "pending filled quantity is invalid"
                )

            if not order_events:
                raise RuntimeError(
                    "pending order evidence is missing"
                )

            matching_orders = [
                event
                for event in order_events
                if event.get("order_id")
                == native_order_id
            ]

            if len(matching_orders) != len(
                order_events
            ):
                raise RuntimeError(
                    "pending order identity mismatch"
                )

            fills = self._native_fills(
                execution_events
            )

            if filled_quantity == 0:
                if fills:
                    raise RuntimeError(
                        "unfilled pending order has executions"
                    )

                native_status = "WORKING"
                fill_confirmed = False

            else:
                if not fills:
                    raise RuntimeError(
                        "partial fill lacks execution evidence"
                    )

                native_status = (
                    "PARTIALLY_FILLED"
                )
                fill_confirmed = True

            return self._base_native(
                client_order_id=operation_id,
                status=native_status,
                resolved=True,
                order={
                    "order_id": native_order_id,
                    "client_order_id": operation_id,
                    "accepted": True,
                    "status": native_status,
                },
                fills=fills,
                fill_confirmed=fill_confirmed,
            )

        if status == "CONFIRMED_EXECUTED":
            if (
                type(native_order_id) is not str
                or not native_order_id
            ):
                raise RuntimeError(
                    "executed native order id is missing"
                )

            if not execution_events:
                raise RuntimeError(
                    "confirmed execution lacks execution evidence"
                )

            fills = self._native_fills(
                execution_events
            )

            expected_count = result.get(
                "execution_count"
            )

            if (
                type(expected_count) is not int
                or expected_count <= 0
                or expected_count != len(fills)
            ):
                raise RuntimeError(
                    "execution evidence count mismatch"
                )

            for fill in fills:
                if (
                    fill["order_id"]
                    != native_order_id
                ):
                    raise RuntimeError(
                        "execution/order identity mismatch"
                    )

            return self._base_native(
                client_order_id=operation_id,
                status="FILLED",
                resolved=True,
                order={
                    "order_id": native_order_id,
                    "client_order_id": operation_id,
                    "accepted": True,
                    "status": "FILLED",
                },
                fills=fills,
                fill_confirmed=True,
            )

        if status == "CONFIRMED_NOT_EXECUTED":
            if (
                type(native_order_id) is not str
                or not native_order_id
            ):
                raise RuntimeError(
                    "terminal native order id is missing"
                )

            terminal = self._terminal_state(
                order_events
            )

            if terminal is None:
                raise RuntimeError(
                    "terminal native state is missing"
                )

            if execution_events:
                raise RuntimeError(
                    "non-executed terminal state has execution evidence"
                )

            native_status = terminal.upper()

            return self._base_native(
                client_order_id=operation_id,
                status=native_status,
                resolved=True,
                order={
                    "order_id": native_order_id,
                    "client_order_id": operation_id,
                    "accepted": False,
                    "status": native_status,
                },
                fills=[],
                fill_confirmed=False,
            )

        raise RuntimeError(
            "unsupported evidence reconciliation status"
        )
