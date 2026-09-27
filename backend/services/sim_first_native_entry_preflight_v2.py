from __future__ import annotations

import re
from typing import Any


class SimFirstNativeEntryPreflightV2:
    """
    Pure fail-closed preflight for the first future native SIM entry.

    This component never submits, modifies, cancels, closes, flattens,
    or otherwise executes an order.

    READY_FOR_OPERATOR_REVIEW means only that prerequisites are
    internally consistent while native submission remains disabled.
    """

    SAFE_ID_PATTERN = re.compile(
        r"^[A-Za-z0-9._-]+$"
    )

    REQUIRED_ACCOUNT = "Sim101"
    REQUIRED_PROVIDER = "Simulator"
    REQUIRED_CONNECTION = "Connected"
    REQUIRED_READINESS = "PHYSICAL_TEST_READY"
    REQUIRED_POSITION = "FLAT"

    @classmethod
    def _valid_identity(
        cls,
        value: Any,
    ) -> bool:
        return (
            type(value) is str
            and bool(value.strip())
            and cls.SAFE_ID_PATTERN.fullmatch(
                value.strip()
            )
            is not None
        )

    def evaluate(
        self,
        *,
        account_name: Any,
        provider: Any,
        connection_status: Any,
        physical_test_readiness: Any,
        position_state: Any,
        active_order_count: Any,
        activation_valid: Any,
        activation_consumed: Any,
        command_id: Any,
        operation_id: Any,
        client_order_id: Any,
        native_submit_enabled: Any,
        auto_retry_allowed: Any,
        recovery_available: Any,
        native_evidence_available: Any,
    ) -> dict[str, object]:
        blocking_reasons: list[str] = []

        if (
            type(account_name) is not str
            or account_name.strip()
            != self.REQUIRED_ACCOUNT
        ):
            blocking_reasons.append(
                "ACCOUNT_NOT_SIM101"
            )

        if (
            type(provider) is not str
            or provider.strip()
            != self.REQUIRED_PROVIDER
        ):
            blocking_reasons.append(
                "PROVIDER_NOT_SIMULATOR"
            )

        if (
            type(connection_status) is not str
            or connection_status.strip()
            != self.REQUIRED_CONNECTION
        ):
            blocking_reasons.append(
                "CONNECTION_NOT_CONNECTED"
            )

        if (
            type(physical_test_readiness)
            is not str
            or physical_test_readiness.strip()
            != self.REQUIRED_READINESS
        ):
            blocking_reasons.append(
                "PHYSICAL_TEST_NOT_READY"
            )

        if (
            type(position_state) is not str
            or position_state.strip().upper()
            != self.REQUIRED_POSITION
        ):
            blocking_reasons.append(
                "POSITION_NOT_FLAT"
            )

        if (
            type(active_order_count) is not int
            or isinstance(
                active_order_count,
                bool,
            )
            or active_order_count < 0
        ):
            blocking_reasons.append(
                "ACTIVE_ORDER_COUNT_INVALID"
            )
        elif active_order_count != 0:
            blocking_reasons.append(
                "ACTIVE_NATIVE_ORDERS_PRESENT"
            )

        if activation_valid is not True:
            blocking_reasons.append(
                "ACTIVATION_INVALID"
            )

        if activation_consumed is not False:
            blocking_reasons.append(
                "ACTIVATION_ALREADY_CONSUMED"
            )

        command_valid = self._valid_identity(
            command_id
        )

        if not command_valid:
            blocking_reasons.append(
                "COMMAND_ID_INVALID"
            )

        operation_valid = self._valid_identity(
            operation_id
        )

        client_valid = self._valid_identity(
            client_order_id
        )

        if (
            not operation_valid
            or not client_valid
            or (
                operation_valid
                and client_valid
                and operation_id.strip()
                != client_order_id.strip()
            )
        ):
            blocking_reasons.append(
                "DURABLE_IDENTITY_MISMATCH"
            )

        if native_submit_enabled is not False:
            blocking_reasons.append(
                "NATIVE_SUBMIT_ALREADY_ENABLED"
            )

        if auto_retry_allowed is not False:
            blocking_reasons.append(
                "AUTO_RETRY_NOT_FORBIDDEN"
            )

        if recovery_available is not True:
            blocking_reasons.append(
                "RECOVERY_UNAVAILABLE"
            )

        if native_evidence_available is not True:
            blocking_reasons.append(
                "NATIVE_EVIDENCE_UNAVAILABLE"
            )

        eligible = not blocking_reasons

        return {
            "status": (
                "READY_FOR_OPERATOR_REVIEW"
                if eligible
                else "BLOCKED"
            ),
            "eligible": eligible,
            "blocking_reasons": (
                blocking_reasons
            ),
            "native_submit_enabled": False,
            "automatic_retry_allowed": False,
            "account_name": (
                account_name.strip()
                if type(account_name) is str
                else None
            ),
            "provider": (
                provider.strip()
                if type(provider) is str
                else None
            ),
            "connection_status": (
                connection_status.strip()
                if type(connection_status) is str
                else None
            ),
            "physical_test_readiness": (
                physical_test_readiness.strip()
                if type(
                    physical_test_readiness
                )
                is str
                else None
            ),
            "position_state": (
                position_state.strip().upper()
                if type(position_state) is str
                else None
            ),
            "active_order_count": (
                active_order_count
                if type(active_order_count) is int
                and not isinstance(
                    active_order_count,
                    bool,
                )
                else None
            ),
            "activation_valid": (
                activation_valid is True
            ),
            "activation_consumed": (
                activation_consumed is True
            ),
            "command_id": (
                command_id.strip()
                if command_valid
                else None
            ),
            "operation_id": (
                operation_id.strip()
                if operation_valid
                else None
            ),
            "client_order_id": (
                client_order_id.strip()
                if client_valid
                else None
            ),
            "recovery_available": (
                recovery_available is True
            ),
            "native_evidence_available": (
                native_evidence_available
                is True
            ),
        }
