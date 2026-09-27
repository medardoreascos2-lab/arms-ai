"""Pure SIM pending-operation recovery classifier.

This service never submits, modifies, cancels, or closes native orders.

It maps a durable operation_id to the same client_order_id and asks the
SIM broker connector for native reconciliation evidence.

Automatic resubmission is always forbidden.
"""

from __future__ import annotations

from copy import deepcopy


class SimPendingOperationRecoveryV2:
    """Fail-closed classifier for a durable SIM pending operation."""

    VALID_NON_TERMINAL = {
        "ACKNOWLEDGED",
        "WORKING",
        "PARTIALLY_FILLED",
    }

    VALID_NOT_EXECUTED = {
        "REJECTED",
        "CANCELLED",
    }

    def __init__(
        self,
        *,
        broker_connector,
    ) -> None:
        if broker_connector is None:
            raise TypeError(
                "broker_connector is required."
            )

        if (
            str(
                getattr(
                    broker_connector,
                    "execution_mode",
                    "",
                )
            )
            .strip()
            .upper()
            != "SIM"
        ):
            raise TypeError(
                "SIM broker connector is required."
            )

        if not callable(
            getattr(
                broker_connector,
                "reconcile_order",
                None,
            )
        ):
            raise TypeError(
                "broker_connector must support reconcile_order."
            )

        self.broker_connector = broker_connector

    @staticmethod
    def _report(
        *,
        status: str,
        resolved: bool,
        operation_id: str,
        native_status: str | None,
        executed: bool,
        reason: str,
        native,
    ) -> dict[str, object]:
        return {
            "status": status,
            "resolved": resolved,
            "operation_id": operation_id,
            "native_status": native_status,
            "executed": executed,
            "reason": reason,
            "native": deepcopy(native),
        }

    def reconcile(
        self,
        *,
        operation_id: str,
    ) -> dict[str, object]:
        if (
            type(operation_id) is not str
            or not operation_id.strip()
        ):
            raise ValueError(
                "operation_id is required."
            )

        normalized_operation_id = (
            operation_id.strip()
        )

        try:
            native = (
                self.broker_connector.reconcile_order(
                    client_order_id=(
                        normalized_operation_id
                    ),
                )
            )
        except RuntimeError as error:
            return self._report(
                status="AMBIGUOUS",
                resolved=False,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=None,
                executed=False,
                reason=str(error),
                native=None,
            )

        except Exception as error:
            return self._report(
                status="CORRUPT",
                resolved=False,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=None,
                executed=False,
                reason=str(error),
                native=None,
            )

        if type(native) is not dict:
            return self._report(
                status="CORRUPT",
                resolved=False,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=None,
                executed=False,
                reason=(
                    "invalid_native_reconciliation_shape"
                ),
                native=None,
            )

        if (
            native.get("client_order_id")
            != normalized_operation_id
        ):
            return self._report(
                status="AMBIGUOUS",
                resolved=False,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=(
                    native.get("status")
                    if type(native.get("status"))
                    is str
                    else None
                ),
                executed=False,
                reason=(
                    "native_client_order_identity_"
                    "does_not_match_durable_operation"
                ),
                native=native,
            )

        native_status = native.get("status")

        if type(native_status) is not str:
            return self._report(
                status="CORRUPT",
                resolved=False,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=None,
                executed=False,
                reason=(
                    "native_status_missing_or_invalid"
                ),
                native=native,
            )

        if native_status == "NOT_FOUND":
            return self._report(
                status="RECOVERY_REQUIRED",
                resolved=False,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=native_status,
                executed=False,
                reason=(
                    "native_order_not_found;"
                    " automatic_resubmit_forbidden"
                ),
                native=None,
            )

        if native_status in self.VALID_NON_TERMINAL:
            return self._report(
                status="PENDING_NATIVE",
                resolved=False,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=native_status,
                executed=False,
                reason=(
                    "native_order_remains_non_terminal"
                ),
                native=native,
            )

        if native_status == "FILLED":
            if (
                native.get("fill_confirmed")
                is not True
                or not isinstance(
                    native.get("fills"),
                    list,
                )
                or not native["fills"]
            ):
                return self._report(
                    status="AMBIGUOUS",
                    resolved=False,
                    operation_id=(
                        normalized_operation_id
                    ),
                    native_status=native_status,
                    executed=False,
                    reason=(
                        "filled_without_confirmed_"
                        "native_fill"
                    ),
                    native=native,
                )

            return self._report(
                status="CONFIRMED_EXECUTED",
                resolved=True,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=native_status,
                executed=True,
                reason=(
                    "native_fill_confirms_execution"
                ),
                native=native,
            )

        if native_status in self.VALID_NOT_EXECUTED:
            return self._report(
                status="CONFIRMED_NOT_EXECUTED",
                resolved=True,
                operation_id=(
                    normalized_operation_id
                ),
                native_status=native_status,
                executed=False,
                reason=(
                    "native_terminal_state_confirms_"
                    "no_execution"
                ),
                native=native,
            )

        return self._report(
            status="AMBIGUOUS",
            resolved=False,
            operation_id=(
                normalized_operation_id
            ),
            native_status=native_status,
            executed=False,
            reason=(
                "unsupported_native_recovery_state"
            ),
            native=native,
        )
