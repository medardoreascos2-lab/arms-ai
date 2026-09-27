from __future__ import annotations

from typing import Any


class SimNativeOrderExecutionReconcilerV2:
    PENDING_STATES = {
        "Initialized",
        "Submitted",
        "Accepted",
        "Working",
        "PartFilled",
    }

    TERMINAL_EXECUTED = "Filled"

    TERMINAL_NOT_EXECUTED = {
        "Rejected",
        "Cancelled",
    }

    def __init__(
        self,
        *,
        evidence_reader: Any,
    ) -> None:
        if evidence_reader is None:
            raise RuntimeError(
                "evidence_reader is required"
            )

        self._reader = evidence_reader

    @staticmethod
    def _base_result(
        *,
        status: str,
        resolved: bool,
        native_order_id: str | None,
        filled_quantity: int,
        execution_count: int,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "resolved": resolved,
            "automatic_retry_allowed": False,
            "native_order_id": native_order_id,
            "filled_quantity": filled_quantity,
            "execution_count": execution_count,
        }

    def reconcile(
        self,
        *,
        command_id: str,
        operation_id: str,
        client_order_id: str,
    ) -> dict[str, Any]:
        events = self._reader.read_for_command(
            command_id=command_id,
            operation_id=operation_id,
            client_order_id=client_order_id,
        )

        if not events:
            return self._base_result(
                status="RECOVERY_REQUIRED",
                resolved=False,
                native_order_id=None,
                filled_quantity=0,
                execution_count=0,
            )

        order_events = [
            event
            for event in events
            if event.get("event_type")
            == "ORDER_UPDATE"
        ]

        execution_events = [
            event
            for event in events
            if event.get("event_type")
            == "EXECUTION_UPDATE"
        ]

        if not order_events:
            raise RuntimeError(
                "execution evidence exists without order evidence"
            )

        native_order_ids = {
            event["order_id"]
            for event in order_events
        }

        if len(native_order_ids) != 1:
            raise RuntimeError(
                "multiple native order ids detected"
            )

        native_order_id = next(
            iter(native_order_ids)
        )

        quantities = {
            event["quantity"]
            for event in order_events
        }

        if len(quantities) != 1:
            raise RuntimeError(
                "native order quantities are inconsistent"
            )

        order_quantity = next(
            iter(quantities)
        )

        if order_quantity <= 0:
            raise RuntimeError(
                "native order quantity is invalid"
            )

        # Evidence files are immutable snapshots, but filename sorting
        # is not a valid source of temporal order. Use conservative
        # state precedence instead of assuming lexical chronology.
        states = {
            event["order_state"]
            for event in order_events
        }

        filled_values = {
            event["filled"]
            for event in order_events
        }

        if any(
            filled < 0 or filled > order_quantity
            for filled in filled_values
        ):
            raise RuntimeError(
                "native order filled quantity is invalid"
            )

        execution_ids: set[str] = set()
        execution_quantity = 0

        for event in execution_events:
            execution_id = event["execution_id"]

            if execution_id in execution_ids:
                raise RuntimeError(
                    "duplicate native execution id"
                )

            execution_ids.add(
                execution_id
            )

            if (
                event["order_id"]
                != native_order_id
            ):
                raise RuntimeError(
                    "execution/order identity mismatch"
                )

            quantity = event["quantity"]

            if quantity <= 0:
                raise RuntimeError(
                    "execution quantity is invalid"
                )

            execution_quantity += quantity

        max_filled = max(
            filled_values,
            default=0,
        )

        if execution_quantity > order_quantity:
            raise RuntimeError(
                "execution quantity exceeds order quantity"
            )

        if execution_quantity != max_filled:
            # For states that claim no fill, executions must not exist.
            # For PartFilled/Filled, execution evidence must exactly
            # corroborate the filled quantity.
            if (
                execution_quantity != 0
                or max_filled != 0
            ):
                raise RuntimeError(
                    "execution quantity does not match filled quantity"
                )

        if "Rejected" in states:
            if (
                len(states) != 1
                or execution_events
                or max_filled != 0
            ):
                raise RuntimeError(
                    "rejected order has contradictory evidence"
                )

            return self._base_result(
                status="CONFIRMED_NOT_EXECUTED",
                resolved=True,
                native_order_id=native_order_id,
                filled_quantity=0,
                execution_count=0,
            )

        if "Cancelled" in states:
            if execution_events or max_filled != 0:
                raise RuntimeError(
                    "cancelled order has execution evidence"
                )

            if "Filled" in states or "PartFilled" in states:
                raise RuntimeError(
                    "cancelled order has contradictory fill state"
                )

            return self._base_result(
                status="CONFIRMED_NOT_EXECUTED",
                resolved=True,
                native_order_id=native_order_id,
                filled_quantity=0,
                execution_count=0,
            )

        if "Filled" in states:
            if max_filled != order_quantity:
                raise RuntimeError(
                    "filled state does not match order quantity"
                )

            if not execution_events:
                raise RuntimeError(
                    "filled order lacks execution evidence"
                )

            if execution_quantity != order_quantity:
                raise RuntimeError(
                    "filled execution quantity mismatch"
                )

            return self._base_result(
                status="CONFIRMED_EXECUTED",
                resolved=True,
                native_order_id=native_order_id,
                filled_quantity=order_quantity,
                execution_count=len(
                    execution_events
                ),
            )

        if "PartFilled" in states:
            if (
                max_filled <= 0
                or max_filled >= order_quantity
            ):
                raise RuntimeError(
                    "part-filled quantity is invalid"
                )

            if not execution_events:
                raise RuntimeError(
                    "part-filled order lacks execution evidence"
                )

            if execution_quantity != max_filled:
                raise RuntimeError(
                    "part-filled execution quantity mismatch"
                )

            return self._base_result(
                status="PENDING_NATIVE",
                resolved=False,
                native_order_id=native_order_id,
                filled_quantity=max_filled,
                execution_count=len(
                    execution_events
                ),
            )

        if states.issubset(
            self.PENDING_STATES
        ):
            if execution_events or max_filled != 0:
                raise RuntimeError(
                    "pending order has contradictory execution evidence"
                )

            return self._base_result(
                status="PENDING_NATIVE",
                resolved=False,
                native_order_id=native_order_id,
                filled_quantity=0,
                execution_count=0,
            )

        raise RuntimeError(
            "native evidence state is unresolved or contradictory"
        )
