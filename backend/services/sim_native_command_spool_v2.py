"""Offline durable spool for native SIM commands and ACK evidence.

No broker or NinjaTrader transport exists in this module.

Command and ACK files are create-once. Repeating identical evidence is
idempotent; conflicting evidence fails closed.

A command without ACK is UNKNOWN and must be reconciled before retry.
"""

from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import re


class SimNativeCommandSpoolV2:
    _SAFE_ID = re.compile(
        r"^[A-Za-z0-9._-]+$"
    )

    def __init__(
        self,
        *,
        root,
    ) -> None:
        self.root = Path(root).resolve()

        self.commands_dir = (
            self.root / "commands"
        )
        self.acks_dir = (
            self.root / "acks"
        )

        self.commands_dir.mkdir(
            parents=True,
            exist_ok=True,
        )
        self.acks_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def _canonical(
        value: dict[str, object],
    ) -> bytes:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )

    @classmethod
    def _validate_id(
        cls,
        value,
        *,
        field: str,
    ) -> str:
        if (
            type(value) is not str
            or not value.strip()
        ):
            raise ValueError(
                f"{field} is required."
            )

        normalized = value.strip()

        if not cls._SAFE_ID.fullmatch(
            normalized
        ):
            raise ValueError(
                f"{field} is invalid."
            )

        return normalized

    @classmethod
    def _validate_command(
        cls,
        command,
    ) -> dict[str, object]:
        if type(command) is not dict:
            raise ValueError(
                "invalid native SIM command."
            )

        try:
            command_id = cls._validate_id(
                command.get("command_id"),
                field="command_id",
            )
            operation_id = cls._validate_id(
                command.get("operation_id"),
                field="operation_id",
            )
            client_order_id = cls._validate_id(
                command.get(
                    "client_order_id"
                ),
                field="client_order_id",
            )
        except ValueError as error:
            raise ValueError(
                "invalid native SIM command."
            ) from error

        if (
            command.get("command")
            != "SUBMIT_ORDER"
            or operation_id
            != client_order_id
            or type(
                command.get("payload")
            ) is not dict
            or not command["payload"]
        ):
            raise ValueError(
                "invalid native SIM command."
            )

        normalized = deepcopy(command)
        normalized["command_id"] = (
            command_id
        )
        normalized["operation_id"] = (
            operation_id
        )
        normalized["client_order_id"] = (
            client_order_id
        )

        return normalized

    @classmethod
    def _validate_ack_shape(
        cls,
        native_ack,
    ) -> dict[str, object]:
        if type(native_ack) is not dict:
            raise RuntimeError(
                "invalid native SIM ack evidence."
            )

        try:
            command_id = cls._validate_id(
                native_ack.get("command_id"),
                field="command_id",
            )
            operation_id = cls._validate_id(
                native_ack.get(
                    "operation_id"
                ),
                field="operation_id",
            )
            client_order_id = cls._validate_id(
                native_ack.get(
                    "client_order_id"
                ),
                field="client_order_id",
            )
        except ValueError as error:
            raise RuntimeError(
                "invalid native SIM ack evidence."
            ) from error

        status = native_ack.get("status")
        accepted = native_ack.get(
            "accepted"
        )
        order_id = native_ack.get(
            "order_id"
        )

        if (
            status
            not in {
                "ACKNOWLEDGED",
                "REJECTED",
            }
            or type(accepted) is not bool
            or type(order_id) is not str
            or not order_id.strip()
        ):
            raise RuntimeError(
                "invalid native SIM ack evidence."
            )

        if (
            status == "ACKNOWLEDGED"
            and accepted is not True
        ):
            raise RuntimeError(
                "invalid native SIM ack evidence."
            )

        if (
            status == "REJECTED"
            and accepted is not False
        ):
            raise RuntimeError(
                "invalid native SIM ack evidence."
            )

        forbidden = {
            "fill_id",
            "filled_price",
            "position_id",
            "broker_position_id",
        }

        if forbidden & set(native_ack):
            raise RuntimeError(
                "invalid native SIM ack evidence."
            )

        normalized = deepcopy(
            native_ack
        )
        normalized["command_id"] = (
            command_id
        )
        normalized["operation_id"] = (
            operation_id
        )
        normalized["client_order_id"] = (
            client_order_id
        )

        return normalized

    def _command_path(
        self,
        command_id: str,
    ) -> Path:
        normalized = self._validate_id(
            command_id,
            field="command_id",
        )

        return (
            self.commands_dir
            / f"{normalized}.json"
        )

    def _ack_path(
        self,
        command_id: str,
    ) -> Path:
        normalized = self._validate_id(
            command_id,
            field="command_id",
        )

        return (
            self.acks_dir
            / f"{normalized}.json"
        )

    @staticmethod
    def _create_once(
        *,
        path: Path,
        payload: bytes,
        collision_message: str,
        durability_error_message: str,
    ) -> tuple[bool, bool]:
        try:
            with path.open("xb") as handle:
                handle.write(payload)
                handle.flush()

                try:
                    os.fsync(
                        handle.fileno()
                    )
                except OSError as error:
                    # Preserve the file as uncertain evidence.
                    # Never report durable success after fsync failure.
                    raise RuntimeError(
                        durability_error_message
                    ) from error

            return True, False

        except FileExistsError:
            try:
                existing = path.read_bytes()
            except OSError as error:
                raise RuntimeError(
                    collision_message
                ) from error

            if existing == payload:
                return False, True

            raise RuntimeError(
                collision_message
            )

    def write_command(
        self,
        *,
        command,
    ) -> dict[str, object]:
        normalized = (
            self._validate_command(
                command
            )
        )

        command_id = normalized[
            "command_id"
        ]

        path = self._command_path(
            command_id
        )

        created, idempotent = (
            self._create_once(
                path=path,
                payload=self._canonical(
                    normalized
                ),
                collision_message=(
                    "command identity collision."
                ),
                durability_error_message=(
                    "command durability sync failed."
                ),
            )
        )

        return {
            "created": created,
            "idempotent": idempotent,
            "command_id": command_id,
            "path": str(path),
        }

    def read_command(
        self,
        *,
        command_id: str,
    ) -> dict[str, object] | None:
        path = self._command_path(
            command_id
        )

        if not path.is_file():
            return None

        try:
            raw = json.loads(
                path.read_text(
                    encoding="utf-8",
                )
            )
            return self._validate_command(
                raw
            )
        except Exception as error:
            raise RuntimeError(
                "corrupt command evidence."
            ) from error

    def write_ack(
        self,
        *,
        native_ack,
    ) -> dict[str, object]:
        normalized = (
            self._validate_ack_shape(
                native_ack
            )
        )

        command_id = normalized[
            "command_id"
        ]

        command = self.read_command(
            command_id=command_id,
        )

        if command is None:
            raise RuntimeError(
                "command evidence not found."
            )

        if (
            normalized["command_id"]
            != command["command_id"]
            or normalized["operation_id"]
            != command["operation_id"]
            or normalized[
                "client_order_id"
            ]
            != command[
                "client_order_id"
            ]
        ):
            raise RuntimeError(
                "ack identity does not match command."
            )

        path = self._ack_path(
            command_id
        )

        created, idempotent = (
            self._create_once(
                path=path,
                payload=self._canonical(
                    normalized
                ),
                collision_message=(
                    "ack evidence collision."
                ),
                durability_error_message=(
                    "ack durability sync failed."
                ),
            )
        )

        return {
            "created": created,
            "idempotent": idempotent,
            "command_id": command_id,
            "path": str(path),
        }

    def read_ack(
        self,
        *,
        command_id: str,
    ) -> dict[str, object] | None:
        command = self.read_command(
            command_id=command_id,
        )

        if command is None:
            return None

        path = self._ack_path(
            command["command_id"]
        )

        if not path.is_file():
            return None

        try:
            native_ack = json.loads(
                path.read_text(
                    encoding="utf-8",
                )
            )

            normalized = (
                self._validate_ack_shape(
                    native_ack
                )
            )
        except Exception as error:
            raise RuntimeError(
                "corrupt ack evidence."
            ) from error

        if (
            normalized["command_id"]
            != command["command_id"]
            or normalized["operation_id"]
            != command["operation_id"]
            or normalized[
                "client_order_id"
            ]
            != command[
                "client_order_id"
            ]
        ):
            raise RuntimeError(
                "corrupt ack evidence."
            )

        return deepcopy(
            normalized
        )

    def classify_pending(
        self,
        *,
        command_id: str,
    ) -> dict[str, object]:
        command = self.read_command(
            command_id=command_id,
        )

        if command is None:
            raise RuntimeError(
                "command evidence not found."
            )

        native_ack = self.read_ack(
            command_id=command_id,
        )

        if native_ack is None:
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

        return {
            "status": native_ack[
                "status"
            ],
            "resolved": True,
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
            "reconciliation_required": False,
            "ack": deepcopy(
                native_ack
            ),
        }
