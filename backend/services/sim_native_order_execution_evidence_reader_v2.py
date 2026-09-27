from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


class SimNativeOrderExecutionEvidenceReaderV2:
    MAX_FILE_BYTES = 1024 * 1024

    SAFE_ID_PATTERN = re.compile(
        r"^[A-Za-z0-9._-]+$"
    )

    ORDER_EVENT = "ORDER_UPDATE"
    EXECUTION_EVENT = "EXECUTION_UPDATE"

    ORDER_KEYS = {
        "event_type",
        "command_id",
        "operation_id",
        "client_order_id",
        "order_id",
        "order_state",
        "quantity",
        "filled",
        "average_fill_price",
    }

    EXECUTION_KEYS = {
        "event_type",
        "command_id",
        "operation_id",
        "client_order_id",
        "execution_id",
        "order_id",
        "quantity",
        "price",
    }

    VALID_ORDER_STATES = {
        "Initialized",
        "Submitted",
        "Accepted",
        "Working",
        "PartFilled",
        "Filled",
        "Cancelled",
        "Rejected",
    }

    def __init__(
        self,
        *,
        evidence_directory: str | Path,
    ) -> None:
        self._directory = Path(
            evidence_directory
        )

        if not self._directory.exists():
            raise RuntimeError(
                "native evidence directory does not exist"
            )

        if not self._directory.is_dir():
            raise RuntimeError(
                "native evidence path is not a directory"
            )

    @classmethod
    def _validate_identity(
        cls,
        value: Any,
        field: str,
    ) -> str:
        if not isinstance(value, str):
            raise RuntimeError(
                f"{field} must be a string"
            )

        value = value.strip()

        if not value:
            raise RuntimeError(
                f"{field} is required"
            )

        if not cls.SAFE_ID_PATTERN.fullmatch(
            value
        ):
            raise RuntimeError(
                f"{field} is invalid"
            )

        return value

    @staticmethod
    def _reject_constant(
        value: str,
    ) -> None:
        raise RuntimeError(
            f"non-finite JSON number: {value}"
        )

    @staticmethod
    def _object_pairs_no_duplicates(
        pairs: list[tuple[str, Any]],
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}

        for key, value in pairs:
            if key in result:
                raise RuntimeError(
                    f"duplicate JSON key: {key}"
                )

            result[key] = value

        return result

    def _read_json_object(
        self,
        path: Path,
    ) -> dict[str, Any]:
        try:
            stat = path.stat()
        except OSError as exc:
            raise RuntimeError(
                "unable to stat native evidence file"
            ) from exc

        if (
            stat.st_size <= 0
            or stat.st_size > self.MAX_FILE_BYTES
        ):
            raise RuntimeError(
                "native evidence file size is invalid"
            )

        try:
            raw = path.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as exc:
            raise RuntimeError(
                "unable to read native evidence file"
            ) from exc

        try:
            payload = json.loads(
                raw,
                parse_constant=self._reject_constant,
                object_pairs_hook=(
                    self._object_pairs_no_duplicates
                ),
            )
        except RuntimeError:
            raise
        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise RuntimeError(
                "native evidence JSON is invalid"
            ) from exc

        if not isinstance(payload, dict):
            raise RuntimeError(
                "native evidence JSON must be an object"
            )

        return payload

    @staticmethod
    def _require_exact_keys(
        payload: dict[str, Any],
        expected: set[str],
    ) -> None:
        actual = set(payload)

        if actual != expected:
            raise RuntimeError(
                "native evidence fields are invalid"
            )

    @staticmethod
    def _require_int(
        value: Any,
        field: str,
        *,
        minimum: int,
    ) -> int:
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < minimum
        ):
            raise RuntimeError(
                f"{field} is invalid"
            )

        return value

    @staticmethod
    def _require_finite_number(
        value: Any,
        field: str,
        *,
        minimum: float,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(
                value,
                (int, float),
            )
        ):
            raise RuntimeError(
                f"{field} is invalid"
            )

        number = float(value)

        if (
            not math.isfinite(number)
            or number < minimum
        ):
            raise RuntimeError(
                f"{field} is invalid"
            )

        return number

    def _validate_common_identity(
        self,
        payload: dict[str, Any],
        *,
        command_id: str,
        operation_id: str,
        client_order_id: str,
    ) -> None:
        evidence_command_id = (
            self._validate_identity(
                payload.get("command_id"),
                "command_id",
            )
        )

        evidence_operation_id = (
            self._validate_identity(
                payload.get("operation_id"),
                "operation_id",
            )
        )

        evidence_client_order_id = (
            self._validate_identity(
                payload.get("client_order_id"),
                "client_order_id",
            )
        )

        if (
            evidence_command_id != command_id
            or evidence_operation_id
            != operation_id
            or evidence_client_order_id
            != client_order_id
        ):
            raise RuntimeError(
                "native evidence identity mismatch"
            )

        if (
            evidence_operation_id
            != evidence_client_order_id
        ):
            raise RuntimeError(
                "native evidence durable identity mismatch"
            )

    def _validate_order_update(
        self,
        payload: dict[str, Any],
        *,
        command_id: str,
        operation_id: str,
        client_order_id: str,
    ) -> dict[str, Any]:
        self._require_exact_keys(
            payload,
            self.ORDER_KEYS,
        )

        self._validate_common_identity(
            payload,
            command_id=command_id,
            operation_id=operation_id,
            client_order_id=client_order_id,
        )

        order_id = self._validate_identity(
            payload["order_id"],
            "order_id",
        )

        state = payload["order_state"]

        if (
            not isinstance(state, str)
            or state
            not in self.VALID_ORDER_STATES
        ):
            raise RuntimeError(
                "order_state is invalid"
            )

        quantity = self._require_int(
            payload["quantity"],
            "quantity",
            minimum=1,
        )

        filled = self._require_int(
            payload["filled"],
            "filled",
            minimum=0,
        )

        if filled > quantity:
            raise RuntimeError(
                "filled exceeds quantity"
            )

        average_fill_price = (
            self._require_finite_number(
                payload["average_fill_price"],
                "average_fill_price",
                minimum=0.0,
            )
        )

        result = dict(payload)
        result["order_id"] = order_id
        result["quantity"] = quantity
        result["filled"] = filled
        result["average_fill_price"] = (
            average_fill_price
        )

        return result

    def _validate_execution_update(
        self,
        payload: dict[str, Any],
        *,
        command_id: str,
        operation_id: str,
        client_order_id: str,
    ) -> dict[str, Any]:
        self._require_exact_keys(
            payload,
            self.EXECUTION_KEYS,
        )

        self._validate_common_identity(
            payload,
            command_id=command_id,
            operation_id=operation_id,
            client_order_id=client_order_id,
        )

        execution_id = self._validate_identity(
            payload["execution_id"],
            "execution_id",
        )

        order_id = self._validate_identity(
            payload["order_id"],
            "order_id",
        )

        quantity = self._require_int(
            payload["quantity"],
            "quantity",
            minimum=1,
        )

        price = self._require_finite_number(
            payload["price"],
            "price",
            minimum=0.0,
        )

        result = dict(payload)
        result["execution_id"] = execution_id
        result["order_id"] = order_id
        result["quantity"] = quantity
        result["price"] = price

        return result

    def read_for_command(
        self,
        *,
        command_id: str,
        operation_id: str,
        client_order_id: str,
    ) -> list[dict[str, Any]]:
        command_id = self._validate_identity(
            command_id,
            "command_id",
        )

        operation_id = self._validate_identity(
            operation_id,
            "operation_id",
        )

        client_order_id = self._validate_identity(
            client_order_id,
            "client_order_id",
        )

        if operation_id != client_order_id:
            raise RuntimeError(
                "operation/client durable identity mismatch"
            )

        prefix = command_id + "."

        candidates = sorted(
            path
            for path in self._directory.iterdir()
            if (
                path.is_file()
                and path.name.startswith(prefix)
                and path.name.endswith(".json")
            )
        )

        events: list[dict[str, Any]] = []

        for path in candidates:
            payload = self._read_json_object(
                path
            )

            event_type = payload.get(
                "event_type"
            )

            if event_type == self.ORDER_EVENT:
                event = self._validate_order_update(
                    payload,
                    command_id=command_id,
                    operation_id=operation_id,
                    client_order_id=client_order_id,
                )

            elif event_type == self.EXECUTION_EVENT:
                event = (
                    self._validate_execution_update(
                        payload,
                        command_id=command_id,
                        operation_id=operation_id,
                        client_order_id=client_order_id,
                    )
                )

            else:
                raise RuntimeError(
                    "native evidence event_type is invalid"
                )

            events.append(event)

        return events
