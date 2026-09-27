"""Offline native SIM command consumer contract.

This consumer reads durable command evidence, invokes an injected executor
exactly once for a command without ACK, validates the returned ACK, and
persists that ACK through the spool.

If native execution raises, the outcome becomes UNKNOWN and the same
consumer instance will not automatically re-execute that command.

No real NinjaTrader transport is implemented here.
"""

from __future__ import annotations

from copy import deepcopy


class SimNativeCommandConsumerV2:
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

    def __init__(
        self,
        *,
        spool,
        executor,
    ) -> None:
        if spool is None:
            raise TypeError(
                "spool is required."
            )

        if executor is None:
            raise TypeError(
                "executor is required."
            )

        for name in (
            "read_command",
            "read_ack",
            "write_ack",
        ):
            if not callable(
                getattr(
                    spool,
                    name,
                    None,
                )
            ):
                raise TypeError(
                    f"spool must provide {name}()."
                )

        if not callable(
            getattr(
                executor,
                "submit_order",
                None,
            )
        ):
            raise TypeError(
                "executor must provide submit_order()."
            )

        self.spool = spool
        self.executor = executor

        # Local uncertainty latch:
        # once execution outcome is unknown, this consumer instance
        # may never re-execute the same command automatically.
        self._unknown_commands = {}

    @staticmethod
    def _validate_command(
        command,
        *,
        requested_command_id: str,
    ) -> dict[str, object]:
        if type(command) is not dict:
            raise RuntimeError(
                "invalid native SIM consumer command."
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
        command_type = command.get(
            "command"
        )
        payload = command.get(
            "payload"
        )

        if (
            type(command_id) is not str
            or not command_id.strip()
            or command_id
            != requested_command_id
            or type(operation_id) is not str
            or not operation_id.strip()
            or type(client_order_id) is not str
            or not client_order_id.strip()
            or operation_id != client_order_id
            or command_type != "SUBMIT_ORDER"
            or type(payload) is not dict
            or not payload
        ):
            raise RuntimeError(
                "invalid native SIM consumer command."
            )

        return deepcopy(
            command
        )

    @classmethod
    def _validate_ack(
        cls,
        *,
        command,
        native_ack,
    ) -> dict[str, object]:
        if type(native_ack) is not dict:
            raise RuntimeError(
                "invalid native SIM consumer acknowledgement."
            )

        command_id = command[
            "command_id"
        ]
        operation_id = command[
            "operation_id"
        ]
        client_order_id = command[
            "client_order_id"
        ]

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
            native_ack.get("command_id")
            != command_id
            or native_ack.get(
                "operation_id"
            )
            != operation_id
            or native_ack.get(
                "client_order_id"
            )
            != client_order_id
            or status
            not in cls.VALID_ACK_STATUSES
            or type(accepted) is not bool
            or type(order_id) is not str
            or not order_id.strip()
        ):
            raise RuntimeError(
                "invalid native SIM consumer acknowledgement."
            )

        if (
            status == "ACKNOWLEDGED"
            and accepted is not True
        ):
            raise RuntimeError(
                "invalid native SIM consumer acknowledgement."
            )

        if (
            status == "REJECTED"
            and accepted is not False
        ):
            raise RuntimeError(
                "invalid native SIM consumer acknowledgement."
            )

        if (
            cls.FORBIDDEN_ACK_FIELDS
            & set(native_ack)
        ):
            raise RuntimeError(
                "invalid native SIM consumer acknowledgement."
            )

        return deepcopy(
            native_ack
        )

    @staticmethod
    def _unknown_report(
        command,
    ) -> dict[str, object]:
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
            "reason": (
                "native_execution_outcome_unknown"
            ),
        }

    def consume(
        self,
        *,
        command_id: str,
    ) -> dict[str, object]:
        if (
            type(command_id) is not str
            or not command_id.strip()
        ):
            raise ValueError(
                "command_id is required."
            )

        normalized_command_id = (
            command_id.strip()
        )

        command = self.spool.read_command(
            command_id=normalized_command_id,
        )

        if command is None:
            raise RuntimeError(
                "command evidence not found."
            )

        command = self._validate_command(
            command,
            requested_command_id=(
                normalized_command_id
            ),
        )

        existing_ack = self.spool.read_ack(
            command_id=normalized_command_id,
        )

        if existing_ack is not None:
            result = self._validate_ack(
                command=command,
                native_ack=existing_ack,
            )

            result[
                "idempotent_replay"
            ] = True

            return result

        if (
            normalized_command_id
            in self._unknown_commands
        ):
            return deepcopy(
                self._unknown_commands[
                    normalized_command_id
                ]
            )

        try:
            native_ack = (
                self.executor.submit_order(
                    prepared_order=deepcopy(
                        command["payload"]
                    ),
                    command_id=command[
                        "command_id"
                    ],
                    operation_id=command[
                        "operation_id"
                    ],
                    client_order_id=command[
                        "client_order_id"
                    ],
                )
            )
        except TimeoutError:
            # A timeout cannot prove whether native execution happened.
            # Latch UNKNOWN and prohibit automatic re-execution.
            unknown = (
                self._unknown_report(
                    command
                )
            )

            self._unknown_commands[
                normalized_command_id
            ] = deepcopy(
                unknown
            )

            return unknown

        except Exception as error:
            # Non-timeout executor failures are contract/runtime failures,
            # not proof of a native execution outcome.
            raise RuntimeError(
                "invalid native SIM consumer acknowledgement."
            ) from error

        validated_ack = (
            self._validate_ack(
                command=command,
                native_ack=native_ack,
            )
        )

        self.spool.write_ack(
            native_ack=validated_ack,
        )

        result = deepcopy(
            validated_ack
        )
        result[
            "idempotent_replay"
        ] = False

        return result
