"""Immutable market snapshots with explicit quote freshness assessment."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class SnapshotState(str, Enum):
    FRESH = "FRESH"
    INCOMPLETE = "INCOMPLETE"
    STALE = "STALE"
    FUTURE = "FUTURE"


def _check_price(value: Decimal | None, name: str) -> None:
    if value is not None and (
        not isinstance(value, Decimal) or not value.is_finite() or value <= 0
    ):
        raise ValueError(f"{name} must be positive and finite when known")


@dataclass(frozen=True)
class MarketSnapshot:
    asset_id: str
    source: str
    timestamp: datetime
    bid: Decimal | None = None
    ask: Decimal | None = None
    last: Decimal | None = None
    volume: Decimal | None = None
    depth_metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.asset_id, str) or not self.asset_id.strip():
            raise ValueError("asset_id must be nonblank")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be nonblank")
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        for name in ("bid", "ask", "last"):
            _check_price(getattr(self, name), name)
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError("bid cannot exceed ask")
        if self.volume is not None and (
            not isinstance(self.volume, Decimal) or not self.volume.is_finite() or self.volume < 0
        ):
            raise ValueError("volume must be nonnegative and finite when known")
        if not isinstance(self.depth_metadata, Mapping) or any(
            not isinstance(k, str) or not k.strip() or not isinstance(v, str)
            for k, v in self.depth_metadata.items()
        ):
            raise ValueError("depth_metadata must contain string keys and values")
        object.__setattr__(self, "depth_metadata", MappingProxyType(dict(self.depth_metadata)))

    def freshness(self, now: datetime, maximum_age: timedelta) -> SnapshotState:
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if not isinstance(maximum_age, timedelta) or maximum_age <= timedelta(0):
            raise ValueError("maximum_age must be positive")
        age = now - self.timestamp
        if age < timedelta(0):
            return SnapshotState.FUTURE
        if age > maximum_age:
            return SnapshotState.STALE
        if self.bid is None or self.ask is None:
            return SnapshotState.INCOMPLETE
        return SnapshotState.FRESH
