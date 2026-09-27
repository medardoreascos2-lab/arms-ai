from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class SimSubmitActivationInspectionSourceV2:
    """
    Read-only inspection source for durable native-SIM submit activation.

    It never arms, consumes, submits, modifies, cancels, closes,
    flattens, or otherwise mutates broker/execution state.
    """

    MAX_FILE_BYTES = 1024 * 1024

    SAFE_ID_PATTERN = re.compile(
        r"^[A-Za-z0-9._-]+$"
    )

    REQUIRED_KEYS = {
        "command_id",
        "operation_id",
        "client_order_id",
        "permit",
        "account",
    }

    REQUIRED_PERMIT = "ONE_SHOT_SIM101_V2"
    REQUIRED_ACCOUNT = "Sim101"

    def __init__(
        self,
        *,
        activation_directory: str | Path,
    ) -> None:
        directory = Path(
            activation_directory
        )

        if not directory.is_absolute():
            raise ValueError(
                "activation_directory must be absolute"
            )

        if (
            not directory.exists()
            or not directory.is_dir()
        ):
            raise ValueError(
                "activation_directory must exist"
            )

        self._activation_directory = (
            directory
        )

    @classmethod
    def _validate_identity(
        cls,
        value: Any,
        label: str,
    ) -> str:
        if value is None:
            raise TypeError(
                f"{label} is required"
            )

        if type(value) is not str:
            raise TypeError(
                f"{label} must be a string"
            )

        normalized = value.strip()

        if (
            not normalized
            or normalized != value
            or cls.SAFE_ID_PATTERN.fullmatch(
                normalized
            )
            is None
        ):
            raise ValueError(
                f"{label} is invalid"
            )

        return normalized

    @staticmethod
    def _object_no_duplicates(
        pairs,
    ):
        result = {}

        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "duplicate JSON key"
                )

            result[key] = value

        return result

    def _activation_path(
        self,
        command_id: str,
    ) -> Path:
        return (
            self._activation_directory
            / f"{command_id}.arm.json"
        )

    def _read_payload(
        self,
        path: Path,
    ) -> dict[str, Any]:
        if not path.exists():
            raise RuntimeError(
                "submit activation evidence is required"
            )

        if not path.is_file():
            raise RuntimeError(
                "submit activation evidence is invalid"
            )

        try:
            size = path.stat().st_size
        except OSError as error:
            raise RuntimeError(
                "submit activation evidence is unavailable"
            ) from error

        if (
            size <= 0
            or size > self.MAX_FILE_BYTES
        ):
            raise RuntimeError(
                "submit activation evidence size is invalid"
            )

        try:
            text = path.read_text(
                encoding="utf-8"
            )

            payload = json.loads(
                text,
                object_pairs_hook=(
                    self._object_no_duplicates
                ),
                parse_constant=lambda value: (
                    (_ for _ in ()).throw(
                        ValueError(
                            "nonfinite JSON"
                        )
                    )
                ),
            )

        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "submit activation evidence is invalid"
            ) from error

        if type(payload) is not dict:
            raise RuntimeError(
                "submit activation evidence must be an object"
            )

        if set(payload) != self.REQUIRED_KEYS:
            raise RuntimeError(
                "submit activation evidence schema is invalid"
            )

        return payload

    def inspect(
        self,
        *,
        command_id: Any,
    ) -> dict[str, object]:
        command_id = self._validate_identity(
            command_id,
            "command_id",
        )

        path = self._activation_path(
            command_id
        )

        payload = self._read_payload(
            path
        )

        file_command_id = (
            self._validate_identity(
                payload["command_id"],
                "activation command_id",
            )
        )

        operation_id = (
            self._validate_identity(
                payload["operation_id"],
                "operation_id",
            )
        )

        client_order_id = (
            self._validate_identity(
                payload["client_order_id"],
                "client_order_id",
            )
        )

        if file_command_id != command_id:
            raise RuntimeError(
                "submit activation command identity mismatch"
            )

        if operation_id != client_order_id:
            raise RuntimeError(
                "submit activation durable identity mismatch"
            )

        permit = payload["permit"]

        if (
            type(permit) is not str
            or permit != self.REQUIRED_PERMIT
        ):
            raise RuntimeError(
                "submit activation permit is invalid"
            )

        account = payload["account"]

        if (
            type(account) is not str
            or account != self.REQUIRED_ACCOUNT
        ):
            raise RuntimeError(
                "submit activation account is invalid"
            )

        consumed_path = Path(
            str(path) + ".consumed"
        )

        return {
            "valid": True,
            "consumed": (
                consumed_path.exists()
            ),
            "command_id": file_command_id,
            "operation_id": operation_id,
            "client_order_id": client_order_id,
            "permit": permit,
            "account": account,
        }
