"""Pure native SIM command protocol.

This module builds durable command identities and validates native ACKs.

It has no transport surface and never submits, modifies, cancels,
or closes native orders.

Timeouts are always UNKNOWN and require reconciliation before any retry.
"""

from __future__ import annotations

from copy import deepcopy


class SimNativeCommandProtocolV2:
    VALID_ACK_STATUSES = {
        "ACKNOWLEDGED",
        "REJECTED",
    }

    FORBIDDEN_ACK_FIELDS = {
        "fill_id",
        "filled_price",
        "position_id",
        "broker_position_id",
    }

    def build_submit_command(
        self,
        *,
        command_id: str,
        operation_id: str,
        client_order_id: str,
        prepared_order,
    ) -> dict[str, object]:
        if (
            type(command_id) is not str
            or not command_id.strip()
        ):
            raise ValueError(
                "command_id is required."
            )

        if (
            type(operation_id) is not str
            or not operation_id.strip()
            or type(client_order_id) is not str
            or not client_order_id.strip()
            or operation_id.strip()
            != client_order_id.strip()
        ):
            raise ValueError(
                "durable submit identity is invalid."
            )

        if (
            type(prepared_order) is not dict
            or not prepared_order
        ):
            raise ValueError(
                "prepared_order is required."
            )

        normalized_command_id = (
            command_id.strip()
        )

        normalized_operation_id = (
            operation_id.strip()
        )

        normalized_client_order_id = (
            client_order_id.strip()
        )

        return {
            "command_id": normalized_command_id,
            "operation_id": normalized_operation_id,
            "command": "SUBMIT_ORDER",
            "client_order_id":
                normalized_client_order_id,
            "payload": deepcopy(
                prepared_order
            ),
        }

    def validate_ack(
        self,
        *,
        command,
        native_ack,
    ) -> dict[str, object]:
        if (
            type(command) is not dict
            or command.get("command")
            != "SUBMIT_ORDER"
        ):
            raise RuntimeError(
                "invalid native SIM command acknowledgement."
            )

        if type(native_ack) is not dict:
            raise RuntimeError(
                "invalid native SIM command acknowledgement."
            )

        command_id = command.get(
            "command_id"
        )
        operation_id = command.get(
            "operation_id"
        )
        client_order_id = command.get(
            "client_order_id"
        )

        native_command_id = native_ack.get(
            "command_id"
        )
        native_operation_id = native_ack.get(
            "operation_id"
        )
        native_client_order_id = native_ack.get(
            "client_order_id"
        )
        status = native_ack.get(
            "status"
        )
        accepted = native_ack.get(
            "accepted"
        )
        order_id = native_ack.get(
            "order_id"
        )

        if (
            type(command_id) is not str
            or not command_id
            or type(operation_id) is not str
            or not operation_id
            or type(client_order_id) is not str
            or not client_order_id
            or native_command_id != command_id
            or native_operation_id != operation_id
            or native_client_order_id
            != client_order_id
            or type(status) is not str
            or status
            not in self.VALID_ACK_STATUSES
            or type(accepted) is not bool
            or type(order_id) is not str
            or not order_id.strip()
        ):
            raise RuntimeError(
                "invalid native SIM command acknowledgement."
            )

        if (
            status == "ACKNOWLEDGED"
            and accepted is not True
        ):
            raise RuntimeError(
                "invalid native SIM command acknowledgement."
            )

        if (
            status == "REJECTED"
            and accepted is not False
        ):
            raise RuntimeError(
                "invalid native SIM command acknowledgement."
            )

        if (
            self.FORBIDDEN_ACK_FIELDS
            & set(native_ack)
        ):
            raise RuntimeError(
                "invalid native SIM command acknowledgement."
            )

        return deepcopy(
            native_ack
        )

    def classify_timeout(
        self,
        *,
        command,
    ) -> dict[str, object]:
        if (
            type(command) is not dict
            or command.get("command")
            != "SUBMIT_ORDER"
            or type(
                command.get("command_id")
            ) is not str
            or not command["command_id"]
            or type(
                command.get("operation_id")
            ) is not str
            or not command["operation_id"]
            or type(
                command.get(
                    "client_order_id"
                )
            ) is not str
            or not command[
                "client_order_id"
            ]
            or command["operation_id"]
            != command["client_order_id"]
        ):
            raise ValueError(
                "invalid native SIM command."
            )

        return {
            "status": "UNKNOWN",
            "resolved": False,
            "command_id": command[
                "command_id"
            ],
            "operation_id": command[
                "operation_id"
            ],
            "client_order_id": command[
                "client_order_id"
            ],
            "automatic_retry_allowed": False,
            "reconciliation_required": True,
        }
