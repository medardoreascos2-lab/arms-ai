from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from math import isfinite
from pathlib import Path
from typing import Any


class SimNativeRuntimeSnapshotReaderV2:
    """
    Strict read-only reader for NinjaTrader native SIM runtime snapshots.

    No execution, mutation, activation consumption, or retry authority.
    """

    SCHEMA = "arms.nt.sim-runtime-readiness.v2"
    FILE_NAME = "sim-native-runtime-snapshot-v2.json"
    MAX_FILE_BYTES = 1024 * 1024

    REQUIRED_KEYS = {
        "schema",
        "observed_at",
        "account_name",
        "provider",
        "connection_status",
        "instrument",
        "physical_test_readiness",
        "position_state",
        "active_order_count",
        "native_submit_enabled",
        "auto_retry_allowed",
    }

    VALID_POSITION_STATES = {
        "FLAT",
        "LONG",
        "SHORT",
        "UNKNOWN",
    }

    VALID_READINESS_STATES = {
        "CONNECTION_NOT_READY",
        "SESSION_STATE_UNKNOWN",
        "MARKET_SESSION_CLOSED",
        "PHYSICAL_TEST_READY",
    }

    def __init__(
        self,
        *,
        snapshot_directory: str | Path,
        instrument: str,
        clock,
        maximum_age_seconds: int | float = 15,
    ) -> None:
        directory = Path(snapshot_directory)

        if not directory.is_absolute():
            raise ValueError(
                "snapshot_directory must be absolute"
            )

        if (
            not directory.exists()
            or not directory.is_dir()
        ):
            raise ValueError(
                "snapshot_directory must exist"
            )

        if (
            type(instrument) is not str
            or not instrument.strip()
            or instrument != instrument.strip()
        ):
            raise ValueError(
                "instrument is invalid"
            )

        if not callable(clock):
            raise TypeError(
                "clock must be callable"
            )

        if (
            type(maximum_age_seconds)
            not in (int, float)
            or isinstance(maximum_age_seconds, bool)
            or not isfinite(maximum_age_seconds)
            or not (
                0
                < float(maximum_age_seconds)
                <= 15
            )
        ):
            raise ValueError(
                "maximum_age_seconds must be within (0, 15]"
            )

        self._directory = directory
        self._instrument = instrument
        self._clock = clock
        self._maximum_age_seconds = float(
            maximum_age_seconds
        )

    @staticmethod
    def _object_no_duplicates(pairs):
        result = {}

        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "duplicate JSON key"
                )

            result[key] = value

        return result

    @staticmethod
    def _reject_constant(value):
        raise ValueError(
            f"nonfinite JSON constant: {value}"
        )

    def _read_payload(
        self,
    ) -> dict[str, Any]:
        path = (
            self._directory
            / self.FILE_NAME
        )

        if not path.exists():
            raise RuntimeError(
                "native runtime snapshot is required"
            )

        if not path.is_file():
            raise RuntimeError(
                "native runtime snapshot is invalid"
            )

        try:
            size = path.stat().st_size
        except OSError as error:
            raise RuntimeError(
                "native runtime snapshot is unavailable"
            ) from error

        if (
            size <= 0
            or size > self.MAX_FILE_BYTES
        ):
            raise RuntimeError(
                "native runtime snapshot size is invalid"
            )

        try:
            payload = json.loads(
                path.read_text(
                    encoding="utf-8"
                ),
                object_pairs_hook=(
                    self._object_no_duplicates
                ),
                parse_constant=(
                    self._reject_constant
                ),
            )
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            ValueError,
        ) as error:
            raise RuntimeError(
                "native runtime snapshot JSON is invalid"
            ) from error

        if type(payload) is not dict:
            raise RuntimeError(
                "native runtime snapshot must be an object"
            )

        if set(payload) != self.REQUIRED_KEYS:
            raise RuntimeError(
                "native runtime snapshot schema fields are invalid"
            )

        return payload

    @staticmethod
    def _require_exact_string(
        value: Any,
        *,
        expected: str,
        field: str,
    ) -> str:
        if (
            type(value) is not str
            or value != expected
        ):
            raise RuntimeError(
                f"{field} identity mismatch"
            )

        return value

    def _validate_time(
        self,
        value: Any,
    ) -> None:
        if type(value) is not str:
            raise RuntimeError(
                "observed_at must be a UTC timestamp"
            )

        try:
            observed = datetime.fromisoformat(
                value.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError as error:
            raise RuntimeError(
                "observed_at is invalid"
            ) from error

        if (
            observed.tzinfo is None
            or observed.utcoffset()
            != timedelta(0)
        ):
            raise RuntimeError(
                "observed_at must be explicit UTC"
            )

        now = self._clock()

        if (
            type(now) is not datetime
            or now.tzinfo is None
            or now.utcoffset()
            != timezone.utc.utcoffset(None)
        ):
            raise RuntimeError(
                "clock must return aware UTC"
            )

        age = (
            now - observed
        ).total_seconds()

        if (
            age < 0
            or age > self._maximum_age_seconds
        ):
            raise RuntimeError(
                "native runtime snapshot is stale or future-dated"
            )

    def snapshot(
        self,
    ) -> dict[str, object]:
        payload = self._read_payload()

        self._require_exact_string(
            payload["schema"],
            expected=self.SCHEMA,
            field="schema",
        )

        self._validate_time(
            payload["observed_at"]
        )

        self._require_exact_string(
            payload["account_name"],
            expected="Sim101",
            field="account_name",
        )

        self._require_exact_string(
            payload["provider"],
            expected="Simulator",
            field="provider",
        )

        self._require_exact_string(
            payload["instrument"],
            expected=self._instrument,
            field="instrument",
        )

        connection_status = payload[
            "connection_status"
        ]

        if type(connection_status) is not str:
            raise RuntimeError(
                "connection_status is invalid"
            )

        readiness = payload[
            "physical_test_readiness"
        ]

        if (
            type(readiness) is not str
            or readiness
            not in self.VALID_READINESS_STATES
        ):
            raise RuntimeError(
                "physical_test_readiness is invalid"
            )

        position_state = payload[
            "position_state"
        ]

        if (
            type(position_state) is not str
            or position_state
            not in self.VALID_POSITION_STATES
        ):
            raise RuntimeError(
                "position_state is invalid"
            )

        active_order_count = payload[
            "active_order_count"
        ]

        if (
            type(active_order_count) is not int
            or isinstance(
                active_order_count,
                bool,
            )
            or active_order_count < 0
        ):
            raise RuntimeError(
                "active_order_count is invalid"
            )

        if (
            payload[
                "native_submit_enabled"
            ]
            is not False
        ):
            raise RuntimeError(
                "native submit must remain disabled"
            )

        if (
            payload[
                "auto_retry_allowed"
            ]
            is not False
        ):
            raise RuntimeError(
                "automatic retry must remain disabled"
            )

        return {
            "account_name": "Sim101",
            "provider": "Simulator",
            "connection_status":
                connection_status,
            "physical_test_readiness":
                readiness,
            "position_state":
                position_state,
            "active_order_count":
                active_order_count,
            "native_submit_enabled": False,
            "auto_retry_allowed": False,
        }
