"""Read-only native SIM operator evidence transport.

This module admits scalar identity evidence only.

It deliberately has:
- no NinjaTrader account objects
- no balances, positions, orders or executions
- no broker connector
- no order API
- no SIM execution authority

A valid record may only feed OperatorSimBindingV2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
import re
import stat
from threading import RLock
from uuid import UUID


SCHEMA = "arms.nt.sim-operator-evidence.v2"
MAX_LINE = 16384
MAX_FILE = 1024 * 1024

_HEX64 = re.compile(r"[0-9a-f]{64}")

_TOP_FIELDS = {
    "schema",
    "session",
    "sequence",
    "observed_at",
    "payload",
}

_PAYLOAD_FIELDS = {
    "installation_ref",
    "account_ref",
    "connection_ref",
    "label_ref",
    "provider",
    "connection_mode",
    "account_count",
    "connected",
    "revoked",
    "runtime_ref",
    "connection_epoch",
}


def _object(pairs):
    value = {}

    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")

        value[key] = item

    return value


def _utc(value):
    if type(value) is not str:
        raise ValueError("UTC timestamp required")

    result = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if result.utcoffset() != timezone.utc.utcoffset(None):
        raise ValueError("explicit UTC required")

    return result


def _local_path(path):
    value = Path(path)

    if (
        not value.is_absolute()
        or str(value).startswith(("\\\\", "//"))
    ):
        raise ValueError("local absolute path required")

    for part in (value, *value.parents):
        if part.exists():
            info = part.lstat()

            if (
                stat.S_ISLNK(info.st_mode)
                or (
                    getattr(
                        info,
                        "st_file_attributes",
                        0,
                    )
                    & 1024
                )
            ):
                raise ValueError(
                    "reparse path forbidden"
                )

    if os.name == "nt":
        import ctypes

        get_type = ctypes.WinDLL(
            "kernel32",
            use_last_error=True,
        ).GetDriveTypeW

        get_type.argtypes = [
            ctypes.c_wchar_p,
        ]
        get_type.restype = ctypes.c_uint

        if get_type(value.anchor) != 3:
            raise ValueError(
                "local fixed drive required"
            )

    return value


def _valid_ref(value):
    return (
        type(value) is str
        and _HEX64.fullmatch(value) is not None
    )


class SimNativeEvidenceReaderV2:
    """Strict, one-way JSONL reader for native SIM identity evidence."""

    def __init__(
        self,
        *,
        path,
        clock,
        maximum_age_seconds=15,
    ):
        if not callable(clock):
            raise TypeError("clock required")

        if (
            type(maximum_age_seconds) not in (int, float)
            or not isfinite(maximum_age_seconds)
            or not 0 < maximum_age_seconds <= 15
        ):
            raise ValueError(
                "bounded SIM evidence age required"
            )

        self.path = _local_path(path)
        self.clock = clock
        self.maximum_age_seconds = float(
            maximum_age_seconds
        )

        self.lock = RLock()

        self.handle = None
        self.identity = None

        self.offset = 0
        self.digest = sha256()

        self.session = None
        self.sequence = -1
        self.last_observed = None

        self.fault = None
        self.stopped = False

    def _fail(self):
        self.fault = (
            "SIM_NATIVE_EVIDENCE_RECOVERY_REQUIRED"
        )

        if self.handle is not None:
            self.handle.close()
            self.handle = None

        raise ValueError(self.fault) from None

    def _open(self):
        info = self.path.stat()

        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_size > MAX_FILE
        ):
            raise ValueError("invalid evidence file")

        self.handle = self.path.open(
            "rb",
            buffering=0,
        )

        opened = os.fstat(
            self.handle.fileno()
        )

        if (
            not opened.st_ino
            or not stat.S_ISREG(opened.st_mode)
        ):
            raise ValueError(
                "file identity unavailable"
            )

        self.identity = (
            opened.st_dev,
            opened.st_ino,
        )

    def _verify_identity(self):
        info = self.path.stat()

        if (
            self.identity
            != (info.st_dev, info.st_ino)
        ):
            raise ValueError("file replaced")

        if (
            info.st_size < self.offset
            or info.st_size > MAX_FILE
        ):
            raise ValueError(
                "file truncated or oversized"
            )

        self.handle.seek(0)

        prefix = self.handle.read(
            self.offset
        )

        if (
            len(prefix) != self.offset
            or sha256(prefix).digest()
            != self.digest.digest()
        ):
            raise ValueError("prefix changed")

        self.handle.seek(
            self.offset
        )

    def _decode(self, raw):
        if (
            not raw
            or not raw.endswith(b"\n")
            or len(raw) > MAX_LINE
        ):
            raise ValueError(
                "complete bounded line required"
            )

        line = raw[:-1]

        if line.endswith(b"\r"):
            line = line[:-1]

        if (
            not line
            or b"\r" in line
        ):
            raise ValueError(
                "malformed line"
            )

        frame = json.loads(
            line.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=lambda _: (
                (_ for _ in ()).throw(
                    ValueError(
                        "nonfinite JSON"
                    )
                )
            ),
        )

        if (
            type(frame) is not dict
            or set(frame) != _TOP_FIELDS
        ):
            raise ValueError(
                "schema fields"
            )

        if frame["schema"] != SCHEMA:
            raise ValueError(
                "schema identity"
            )

        sequence = frame["sequence"]

        if (
            type(sequence) is not int
            or sequence != self.sequence + 1
        ):
            raise ValueError(
                "canonical sequence"
            )

        session = frame["session"]

        if type(session) is not str:
            raise ValueError(
                "session required"
            )

        try:
            canonical_session = str(
                UUID(session)
            )
        except (ValueError, TypeError, AttributeError):
            raise ValueError(
                "invalid session"
            ) from None

        if (
            canonical_session != session
            or (
                self.session is not None
                and session != self.session
            )
        ):
            raise ValueError(
                "session changed"
            )

        observed = _utc(
            frame["observed_at"]
        )

        now = self.clock()

        if (
            type(now) is not datetime
            or now.tzinfo is None
        ):
            raise ValueError(
                "aware clock required"
            )

        if (
            now.utcoffset()
            != timezone.utc.utcoffset(None)
        ):
            raise ValueError(
                "UTC clock required"
            )

        age = (
            now - observed
        ).total_seconds()

        if not (
            0
            <= age
            <= self.maximum_age_seconds
        ):
            raise ValueError(
                "stale or future evidence"
            )

        if (
            self.last_observed is not None
            and observed < self.last_observed
        ):
            raise ValueError(
                "evidence time regressed"
            )

        payload = frame["payload"]

        if (
            type(payload) is not dict
            or set(payload)
            != _PAYLOAD_FIELDS
        ):
            raise ValueError(
                "payload fields"
            )

        for key in (
            "installation_ref",
            "account_ref",
            "connection_ref",
            "label_ref",
        ):
            if not _valid_ref(
                payload[key]
            ):
                raise ValueError(
                    "invalid private reference"
                )

        if (
            payload["provider"] != "Simulator"
            or type(payload["provider"]) is not str
        ):
            raise ValueError(
                "native simulation identity"
            )

        if (
            type(payload["connection_mode"]) is not str
            or payload["connection_mode"]
                not in {"Live", "Simulation"}
        ):
            raise ValueError(
                "connection mode identity"
            )

        if (
            type(payload["account_count"])
            is not int
            or payload["account_count"] != 1
        ):
            raise ValueError(
                "single account required"
            )

        if (
            type(payload["connected"])
            is not bool
            or payload["connected"] is not True
            or type(payload["revoked"])
            is not bool
            or payload["revoked"] is not False
        ):
            raise ValueError(
                "connected non-revoked evidence required"
            )

        for key in (
            "runtime_ref",
            "connection_epoch",
        ):
            value = payload[key]

            if (
                type(value) is not str
                or not value
                or len(value) > 256
            ):
                raise ValueError(
                    "runtime identity required"
                )

        result = {
            "installation_ref":
                payload["installation_ref"],
            "account_ref":
                payload["account_ref"],
            "connection_ref":
                payload["connection_ref"],
            "label_ref":
                payload["label_ref"],
            "provider":
                payload["provider"],
            "connection_mode":
                payload["connection_mode"],
            "account_count":
                payload["account_count"],
            "connected":
                payload["connected"],
            "revoked":
                payload["revoked"],
            "runtime_ref":
                payload["runtime_ref"],
            "connection_epoch":
                payload["connection_epoch"],
            "observed_at":
                frame["observed_at"],
            "discovery_sequence":
                sequence,
        }

        self.session = session
        self.sequence = sequence
        self.last_observed = observed

        return result

    def poll(self):
        with self.lock:
            if (
                self.stopped
                or self.fault is not None
            ):
                raise RuntimeError(
                    "STOPPED or RECOVERY_REQUIRED"
                )

            try:
                if self.handle is None:
                    self._open()
                else:
                    self._verify_identity()

                raw = self.handle.readline(
                    MAX_LINE + 1
                )

                result = self._decode(
                    raw
                )

                self.offset += len(raw)
                self.digest.update(raw)

                return result

            except Exception:
                self._fail()

    def close(self):
        with self.lock:
            self.stopped = True

            if self.handle is not None:
                self.handle.close()
                self.handle = None
