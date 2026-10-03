"""Provider-neutral operational metrics export with no external collector."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import hashlib
import json
import re
from threading import RLock
from types import MappingProxyType
from typing import Mapping, Protocol, runtime_checkable

from .secret_redaction import redact_text, sensitive_key


_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class OperationalMetricName(str, Enum):
    API_HEALTH = "api_health"
    DB_HEALTH = "db_health"
    WORKER_HEALTH = "worker_health"
    QUEUE_DEPTH = "queue_depth"
    OUTBOX_FAILURES = "outbox_failures"
    SNAPSHOT_LAG_SECONDS = "snapshot_lag_seconds"
    EVALUATION_LAG_SECONDS = "evaluation_lag_seconds"
    RESEARCH_QUEUE = "research_queue"
    SCHEDULER_HEARTBEAT = "scheduler_heartbeat"
    AUTH_DENIALS = "auth_denials"
    MIGRATION_STATE = "migration_state"


class MetricUnit(str, Enum):
    HEALTH = "HEALTH"
    COUNT = "COUNT"
    SECONDS = "SECONDS"
    VERSION = "VERSION"


METRIC_UNITS = MappingProxyType({
    OperationalMetricName.API_HEALTH: MetricUnit.HEALTH,
    OperationalMetricName.DB_HEALTH: MetricUnit.HEALTH,
    OperationalMetricName.WORKER_HEALTH: MetricUnit.HEALTH,
    OperationalMetricName.QUEUE_DEPTH: MetricUnit.COUNT,
    OperationalMetricName.OUTBOX_FAILURES: MetricUnit.COUNT,
    OperationalMetricName.SNAPSHOT_LAG_SECONDS: MetricUnit.SECONDS,
    OperationalMetricName.EVALUATION_LAG_SECONDS: MetricUnit.SECONDS,
    OperationalMetricName.RESEARCH_QUEUE: MetricUnit.COUNT,
    OperationalMetricName.SCHEDULER_HEARTBEAT: MetricUnit.HEALTH,
    OperationalMetricName.AUTH_DENIALS: MetricUnit.COUNT,
    OperationalMetricName.MIGRATION_STATE: MetricUnit.VERSION,
})


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError("metric value must be an integer or exact Decimal")
    result = value if isinstance(value, Decimal) else Decimal(value)
    if not result.is_finite() or result < 0:
        raise ValueError("metric value must be finite and nonnegative")
    return result


def safe_dimensions(
    dimensions: Mapping[str, str] | None,
) -> tuple[tuple[str, str], ...]:
    if dimensions is None:
        return ()
    if not isinstance(dimensions, Mapping) or len(dimensions) > 16:
        raise ValueError("metric dimensions must be a bounded mapping")
    safe = []
    for key, value in dimensions.items():
        if (
            not isinstance(key, str)
            or _LABEL.fullmatch(key) is None
            or sensitive_key(key)
        ):
            raise ValueError("metric dimension key is unsafe")
        if (
            not isinstance(value, str)
            or _LABEL.fullmatch(value) is None
            or redact_text(value) != value
        ):
            raise ValueError("metric dimension value is unsafe")
        safe.append((key, value))
    return tuple(sorted(safe))


@dataclass(frozen=True)
class OperationalMetric:
    name: OperationalMetricName
    value: Decimal
    unit: MetricUnit
    observed_at: datetime
    dimensions: tuple[tuple[str, str], ...] = ()
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, OperationalMetricName):
            raise ValueError("name must be an OperationalMetricName")
        if self.unit is not METRIC_UNITS[self.name]:
            raise ValueError("metric unit does not match metric definition")
        value = _decimal(self.value)
        if self.unit is MetricUnit.HEALTH and value not in (Decimal(0), Decimal(1)):
            raise ValueError("health metrics must be zero or one")
        if self.unit in (MetricUnit.COUNT, MetricUnit.VERSION) and value != value.to_integral():
            raise ValueError("count and version metrics must be integers")
        if self.unit is MetricUnit.VERSION and value < 1:
            raise ValueError("migration version must be positive")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))
        if safe_dimensions(dict(self.dimensions)) != self.dimensions:
            raise ValueError("dimensions must already be sorted and safe")


@dataclass(frozen=True)
class OperationalMetricsSnapshot:
    metrics: tuple[OperationalMetric, ...]
    captured_at: datetime
    snapshot_id: str = field(init=False)
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.metrics, tuple) or any(
            not isinstance(metric, OperationalMetric) for metric in self.metrics
        ):
            raise ValueError("metrics must be an immutable metric tuple")
        names = tuple(metric.name for metric in self.metrics)
        expected = tuple(OperationalMetricName)
        if names != expected:
            raise ValueError("snapshot must contain every required metric in canonical order")
        captured = _utc(self.captured_at, "captured_at")
        if any(metric.observed_at > captured for metric in self.metrics):
            raise ValueError("metrics cannot be observed after snapshot capture")
        object.__setattr__(self, "captured_at", captured)
        document = {
            "captured_at": captured.isoformat(),
            "metrics": [
                {
                    "dimensions": metric.dimensions,
                    "name": metric.name.value,
                    "observed_at": metric.observed_at.isoformat(),
                    "unit": metric.unit.value,
                    "value": format(metric.value, "f"),
                }
                for metric in self.metrics
            ],
        }
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        object.__setattr__(self, "snapshot_id", hashlib.sha256(encoded).hexdigest())


def build_operational_metrics_snapshot(
    values: Mapping[OperationalMetricName, int | Decimal],
    *,
    observed_at: datetime,
    captured_at: datetime | None = None,
    dimensions: Mapping[str, str] | None = None,
) -> OperationalMetricsSnapshot:
    if not isinstance(values, Mapping) or set(values) != set(OperationalMetricName):
        raise ValueError("values must contain exactly every required operational metric")
    observed = _utc(observed_at, "observed_at")
    safe = safe_dimensions(dimensions)
    metrics = tuple(
        OperationalMetric(name, values[name], METRIC_UNITS[name], observed, safe)
        for name in OperationalMetricName
    )
    return OperationalMetricsSnapshot(metrics, captured_at or observed)


@dataclass(frozen=True)
class MetricsExportResult:
    provider_id: str
    snapshot_id: str
    exported: bool
    duplicate: bool
    metric_count: int
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


@runtime_checkable
class MetricsExporter(Protocol):
    provider_id: str
    external_export_authorized: bool

    def export(self, snapshot: OperationalMetricsSnapshot) -> MetricsExportResult: ...


class InMemoryMetricsExporter:
    """Bounded local/test sink; it performs no network or filesystem I/O."""

    provider_id = "in_memory"
    external_export_authorized = False
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, *, maximum_snapshots: int = 128):
        if type(maximum_snapshots) is not int or maximum_snapshots < 1:
            raise ValueError("maximum_snapshots must be positive")
        self._maximum = maximum_snapshots
        self._snapshots: dict[str, OperationalMetricsSnapshot] = {}
        self._order: list[str] = []
        self._lock = RLock()

    def export(self, snapshot: OperationalMetricsSnapshot) -> MetricsExportResult:
        if not isinstance(snapshot, OperationalMetricsSnapshot):
            raise ValueError("snapshot must be an OperationalMetricsSnapshot")
        with self._lock:
            duplicate = snapshot.snapshot_id in self._snapshots
            if not duplicate:
                self._snapshots[snapshot.snapshot_id] = snapshot
                self._order.append(snapshot.snapshot_id)
                while len(self._order) > self._maximum:
                    oldest = self._order.pop(0)
                    self._snapshots.pop(oldest, None)
        return MetricsExportResult(
            provider_id=self.provider_id,
            snapshot_id=snapshot.snapshot_id,
            exported=not duplicate,
            duplicate=duplicate,
            metric_count=len(snapshot.metrics),
        )

    def snapshots(self) -> tuple[OperationalMetricsSnapshot, ...]:
        with self._lock:
            return tuple(self._snapshots[item] for item in self._order)
