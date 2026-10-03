"""Reproducible, append-only provenance for research results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import re
from threading import RLock


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")


class ProvenanceConflictError(RuntimeError):
    pass


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} is invalid")
    return value


def _sha(value: object, name: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ResearchProvenanceRecord:
    result_id: str
    result_hash: str
    dataset_hashes: tuple[str, ...]
    strategy_hash: str
    parameter_hash: str
    code_commit: str
    random_seed: int
    config: tuple[tuple[str, str], ...]
    created_at: datetime
    provenance_hash: str = field(init=False)
    reconstructable: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _identifier(self.result_id, "result_id"))
        for name in ("result_hash", "strategy_hash", "parameter_hash"):
            object.__setattr__(self, name, _sha(getattr(self, name), name))
        if not isinstance(self.dataset_hashes, tuple) or not self.dataset_hashes:
            raise ValueError("dataset_hashes must be a nonempty tuple")
        datasets = tuple(sorted(_sha(item, "dataset_hash") for item in self.dataset_hashes))
        if datasets != self.dataset_hashes or len(set(datasets)) != len(datasets):
            raise ValueError("dataset_hashes must be sorted and unique")
        if not isinstance(self.code_commit, str) or _COMMIT.fullmatch(self.code_commit) is None:
            raise ValueError("code_commit must be a full lowercase Git commit")
        if type(self.random_seed) is not int or self.random_seed < 0 or self.random_seed > 2**63 - 1:
            raise ValueError("random_seed must be a nonnegative signed 64-bit integer")
        if not isinstance(self.config, tuple) or not self.config:
            raise ValueError("config must be a nonempty tuple")
        normalized: list[tuple[str, str]] = []
        for item in self.config:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("config contains an invalid item")
            key, value = item
            normalized.append((_identifier(key, "config_key"), value if isinstance(value, str) and value else _raise_config()))
        if tuple(normalized) != tuple(sorted(normalized)) or len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("config must be sorted with unique keys")
        if not isinstance(self.created_at, datetime) or self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        object.__setattr__(self, "created_at", self.created_at.astimezone(timezone.utc))
        object.__setattr__(self, "provenance_hash", _digest(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value = {
            "code_commit": self.code_commit,
            "config": dict(self.config),
            "created_at": self.created_at.isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "dataset_hashes": list(self.dataset_hashes),
            "execution_authorized": self.execution_authorized,
            "parameter_hash": self.parameter_hash,
            "random_seed": self.random_seed,
            "reconstructable": self.reconstructable,
            "result_hash": self.result_hash,
            "result_id": self.result_id,
            "strategy_hash": self.strategy_hash,
        }
        if include_hash:
            value["provenance_hash"] = self.provenance_hash
        return value


def _raise_config() -> str:
    raise ValueError("config values must be nonempty strings")


class ResearchProvenanceRegistry:
    """In-memory append-only identity boundary; persistence is supplied by callers."""

    execution_authorized = False

    def __init__(self) -> None:
        self._records: dict[str, ResearchProvenanceRecord] = {}
        self._lock = RLock()

    def register(self, record: ResearchProvenanceRecord) -> ResearchProvenanceRecord:
        if not isinstance(record, ResearchProvenanceRecord):
            raise ValueError("record must be ResearchProvenanceRecord")
        with self._lock:
            existing = self._records.get(record.result_id)
            if existing is not None and existing.provenance_hash != record.provenance_hash:
                raise ProvenanceConflictError("result_id already has different provenance")
            if existing is None:
                self._records[record.result_id] = record
            return self._records[record.result_id]

    def get(self, result_id: str) -> ResearchProvenanceRecord | None:
        key = _identifier(result_id, "result_id")
        with self._lock:
            return self._records.get(key)

    def list(self) -> tuple[ResearchProvenanceRecord, ...]:
        with self._lock:
            return tuple(self._records[key] for key in sorted(self._records))
