"""Frontend-independent, immutable Phase 3 dashboard projections."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re


_HASH = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
JsonScalar = str | int | bool | None


class DashboardProjectionKind(str, Enum):
    ACCOUNT_STATUS = "ACCOUNT_STATUS"
    PROP_FIRM_STATUS = "PROP_FIRM_STATUS"
    PORTFOLIO = "PORTFOLIO"
    RESEARCH_RUNS = "RESEARCH_RUNS"
    CHALLENGERS = "CHALLENGERS"
    PROMOTION_REVIEWS = "PROMOTION_REVIEWS"


REQUIRED_FIELDS = {
    DashboardProjectionKind.ACCOUNT_STATUS: frozenset({"account_id", "state", "equity", "trading_blocked"}),
    DashboardProjectionKind.PROP_FIRM_STATUS: frozenset({"profile_id", "status", "daily_loss_remaining", "drawdown_remaining", "payout_eligible"}),
    DashboardProjectionKind.PORTFOLIO: frozenset({"total_equity", "realized_pnl", "unrealized_pnl", "open_positions", "exposure"}),
    DashboardProjectionKind.RESEARCH_RUNS: frozenset({"run_id", "status", "started_at", "result_hash"}),
    DashboardProjectionKind.CHALLENGERS: frozenset({"strategy_id", "status", "revision", "evidence_hash"}),
    DashboardProjectionKind.PROMOTION_REVIEWS: frozenset({"review_id", "candidate_id", "status", "review_hash", "human_decision_required"}),
}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class DashboardProjection:
    projection_id: str
    kind: DashboardProjectionKind
    observed_at: datetime
    source_hash: str
    fields: tuple[tuple[str, JsonScalar], ...]
    projection_hash: str = field(init=False)
    read_only: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.projection_id, str) or _ID.fullmatch(self.projection_id) is None:
            raise ValueError("projection_id is invalid")
        if not isinstance(self.kind, DashboardProjectionKind):
            raise ValueError("kind is invalid")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        object.__setattr__(self, "observed_at", self.observed_at.astimezone(timezone.utc))
        if not isinstance(self.source_hash, str) or _HASH.fullmatch(self.source_hash) is None:
            raise ValueError("source_hash must be lowercase SHA-256")
        if not isinstance(self.fields, tuple):
            raise ValueError("fields must be a tuple")
        keys: list[str] = []
        for item in self.fields:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("fields contains an invalid item")
            key, value = item
            if not isinstance(key, str) or _ID.fullmatch(key) is None or type(value) not in {str, int, bool, type(None)}:
                raise ValueError("field keys and values must be JSON scalar contract values")
            keys.append(key)
        if tuple(keys) != tuple(sorted(keys)) or len(set(keys)) != len(keys):
            raise ValueError("fields must be sorted with unique keys")
        if set(keys) != set(REQUIRED_FIELDS[self.kind]):
            raise ValueError("fields do not match the projection contract")
        object.__setattr__(self, "projection_hash", _digest(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value = {"execution_authorized": self.execution_authorized, "fields": dict(self.fields),
                 "kind": self.kind.value, "observed_at": self.observed_at.isoformat(),
                 "projection_id": self.projection_id, "read_only": self.read_only, "source_hash": self.source_hash}
        if include_hash:
            value["projection_hash"] = self.projection_hash
        return value


@dataclass(frozen=True)
class Phase3DashboardBundle:
    generated_at: datetime
    projections: tuple[DashboardProjection, ...]
    bundle_hash: str = field(init=False)
    frontend_independent: bool = field(default=True, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        object.__setattr__(self, "generated_at", self.generated_at.astimezone(timezone.utc))
        kinds = tuple(item.kind for item in self.projections if isinstance(item, DashboardProjection))
        expected = tuple(sorted(DashboardProjectionKind, key=lambda item: item.value))
        if len(kinds) != len(self.projections) or kinds != expected:
            raise ValueError("projections must contain every kind exactly once in sorted order")
        object.__setattr__(self, "bundle_hash", _digest(self.document(include_hash=False)))

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value = {"execution_authorized": self.execution_authorized, "frontend_independent": self.frontend_independent,
                 "generated_at": self.generated_at.isoformat(), "projections": [item.document() for item in self.projections]}
        if include_hash:
            value["bundle_hash"] = self.bundle_hash
        return value
