"""Research-only performance analytics for source-provided regimes and sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class MarketRegimeLabel(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGE = "RANGE"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    NO_TRADE = "NO_TRADE"


class TradingSessionLabel(str, Enum):
    ASIA = "ASIA"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} is invalid")
    return value


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decimal(value: object, name: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite Decimal")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} must be a finite Decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    return number


def _utc_text(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RegimePerformanceObservation:
    observation_id: str
    timestamp: datetime
    net_r: Decimal
    profitable: bool
    regime: MarketRegimeLabel | None = None
    session: TradingSessionLabel | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_id",
            _identifier(self.observation_id, "observation_id"),
        )
        object.__setattr__(self, "timestamp", _utc(self.timestamp, "timestamp"))
        object.__setattr__(self, "net_r", _decimal(self.net_r, "net_r"))
        if type(self.profitable) is not bool:
            raise ValueError("profitable must be bool")
        if self.profitable is not (self.net_r > 0):
            raise ValueError("profitable must equal net_r > 0")
        if self.regime is not None and not isinstance(self.regime, MarketRegimeLabel):
            raise ValueError("regime must be a source-provided MarketRegimeLabel or None")
        if self.session is not None and not isinstance(self.session, TradingSessionLabel):
            raise ValueError("session must be a source-provided TradingSessionLabel or None")

    def document(self) -> dict[str, object]:
        return {
            "net_r": format(self.net_r, "f"),
            "observation_id": self.observation_id,
            "profitable": self.profitable,
            "regime": None if self.regime is None else self.regime.value,
            "session": None if self.session is None else self.session.value,
            "timestamp": _utc_text(self.timestamp),
        }


@dataclass(frozen=True)
class PerformanceBucket:
    label: str
    observation_count: int
    profitable_count: int
    total_net_r: Decimal
    average_net_r: Decimal

    def __post_init__(self) -> None:
        _identifier(self.label, "label")
        if type(self.observation_count) is not int or self.observation_count <= 0:
            raise ValueError("observation_count must be positive")
        if type(self.profitable_count) is not int or not 0 <= self.profitable_count <= self.observation_count:
            raise ValueError("profitable_count is invalid")
        object.__setattr__(self, "total_net_r", _decimal(self.total_net_r, "total_net_r"))
        object.__setattr__(self, "average_net_r", _decimal(self.average_net_r, "average_net_r"))
        if self.average_net_r != self.total_net_r / Decimal(self.observation_count):
            raise ValueError("average_net_r does not reconcile")

    def document(self) -> dict[str, object]:
        return {
            "average_net_r": format(self.average_net_r, "f"),
            "label": self.label,
            "observation_count": self.observation_count,
            "profitable_count": self.profitable_count,
            "total_net_r": format(self.total_net_r, "f"),
        }


@dataclass(frozen=True)
class RegimePerformanceResult:
    generated_at: datetime
    source_hash: str
    regime_buckets: tuple[PerformanceBucket, ...]
    session_buckets: tuple[PerformanceBucket, ...]
    unlabeled_regime_count: int
    unlabeled_session_count: int
    observation_count: int
    result_hash: str = field(init=False)
    inferred_labels_used: bool = field(default=False, init=False)
    strategy_rewrite_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_at", _utc(self.generated_at, "generated_at"))
        if not isinstance(self.source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", self.source_hash) is None:
            raise ValueError("source_hash must be lowercase SHA-256")
        if type(self.observation_count) is not int or self.observation_count <= 0:
            raise ValueError("observation_count must be positive")
        for name, value in (
            ("unlabeled_regime_count", self.unlabeled_regime_count),
            ("unlabeled_session_count", self.unlabeled_session_count),
        ):
            if type(value) is not int or not 0 <= value <= self.observation_count:
                raise ValueError(f"{name} is invalid")
        self._validate_buckets(self.regime_buckets, MarketRegimeLabel, "regime")
        self._validate_buckets(self.session_buckets, TradingSessionLabel, "session")
        if sum(item.observation_count for item in self.regime_buckets) + self.unlabeled_regime_count != self.observation_count:
            raise ValueError("regime counts do not reconcile")
        if sum(item.observation_count for item in self.session_buckets) + self.unlabeled_session_count != self.observation_count:
            raise ValueError("session counts do not reconcile")
        object.__setattr__(self, "result_hash", _hash(self.document(include_hash=False)))

    @staticmethod
    def _validate_buckets(
        buckets: tuple[PerformanceBucket, ...],
        allowed: type[Enum],
        name: str,
    ) -> None:
        if not isinstance(buckets, tuple):
            raise ValueError(f"{name}_buckets must be a tuple")
        labels = tuple(item.label for item in buckets if isinstance(item, PerformanceBucket))
        if len(labels) != len(buckets):
            raise ValueError(f"{name}_buckets contains an invalid bucket")
        if labels != tuple(sorted(labels)) or len(set(labels)) != len(labels):
            raise ValueError(f"{name}_buckets must be sorted with unique labels")
        allowed_values = {item.value for item in allowed}
        if any(label not in allowed_values for label in labels):
            raise ValueError(f"{name}_buckets contains an unsupported label")

    def document(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "execution_authorized": self.execution_authorized,
            "generated_at": _utc_text(self.generated_at),
            "inferred_labels_used": self.inferred_labels_used,
            "observation_count": self.observation_count,
            "regime_buckets": [item.document() for item in self.regime_buckets],
            "session_buckets": [item.document() for item in self.session_buckets],
            "source_hash": self.source_hash,
            "strategy_rewrite_authorized": self.strategy_rewrite_authorized,
            "unlabeled_regime_count": self.unlabeled_regime_count,
            "unlabeled_session_count": self.unlabeled_session_count,
        }
        if include_hash:
            value["result_hash"] = self.result_hash
        return value


class RegimePerformanceAnalytics:
    """Aggregate only labels carried by source observations."""

    def analyze(
        self,
        observations: tuple[RegimePerformanceObservation, ...],
        *,
        generated_at: datetime,
    ) -> RegimePerformanceResult:
        if not isinstance(observations, tuple) or not observations:
            raise ValueError("observations must be a nonempty tuple")
        if any(not isinstance(item, RegimePerformanceObservation) for item in observations):
            raise ValueError("observations contains an invalid item")

        ordered = tuple(sorted(observations, key=lambda item: item.observation_id))
        if len({item.observation_id for item in ordered}) != len(ordered):
            raise ValueError("observation_id values must be unique")

        source_hash = _hash([item.document() for item in ordered])
        regime_buckets = self._aggregate(ordered, "regime")
        session_buckets = self._aggregate(ordered, "session")
        return RegimePerformanceResult(
            generated_at=generated_at,
            source_hash=source_hash,
            regime_buckets=regime_buckets,
            session_buckets=session_buckets,
            unlabeled_regime_count=sum(item.regime is None for item in ordered),
            unlabeled_session_count=sum(item.session is None for item in ordered),
            observation_count=len(ordered),
        )

    @staticmethod
    def _aggregate(
        observations: tuple[RegimePerformanceObservation, ...],
        attribute: str,
    ) -> tuple[PerformanceBucket, ...]:
        groups: dict[str, list[RegimePerformanceObservation]] = {}
        for observation in observations:
            label = getattr(observation, attribute)
            if label is not None:
                groups.setdefault(label.value, []).append(observation)

        buckets: list[PerformanceBucket] = []
        for label, members in sorted(groups.items()):
            total = sum((item.net_r for item in members), Decimal("0"))
            buckets.append(
                PerformanceBucket(
                    label=label,
                    observation_count=len(members),
                    profitable_count=sum(item.profitable for item in members),
                    total_net_r=total,
                    average_net_r=total / Decimal(len(members)),
                )
            )
        return tuple(buckets)
