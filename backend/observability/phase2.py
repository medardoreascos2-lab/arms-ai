"""Isolated structured observability foundation for Phase 2 capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import re
from threading import Lock
from typing import Callable, Mapping, Protocol, TypeAlias


class Phase2TelemetryCategory(str, Enum):
    RULE_EVALUATION = "RULE_EVALUATION"
    PROFILE_FRESHNESS = "PROFILE_FRESHNESS"
    API_CALL = "API_CALL"
    NOTIFICATION = "NOTIFICATION"
    ACCOUNT_ANALYTICS = "ACCOUNT_ANALYTICS"


class Phase2MetricUnit(str, Enum):
    COUNT = "COUNT"
    MILLISECONDS = "MILLISECONDS"
    SECONDS = "SECONDS"


class Phase2EventSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class TelemetryWriteStatus(str, Enum):
    RECORDED = "RECORDED"
    SINK_UNAVAILABLE = "SINK_UNAVAILABLE"


_NAME = re.compile(r"^arms\.phase2\.[a-z][a-z0-9_.]{2,95}$")
_LABEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
_SENSITIVE_KEY_PARTS = (
    "account_id",
    "account_number",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "email",
    "endpoint",
    "exception",
    "header",
    "message",
    "password",
    "payload",
    "phone",
    "private_key",
    "query",
    "request_body",
    "response_body",
    "secret",
    "tenant_id",
    "token",
    "url",
    "user_id",
)
_SENSITIVE_TEXT = re.compile(
    r"(?i)(?:bearer\s+\S+|(?:token|password|secret|api[_-]?key|authorization|"
    r"credential)\s*[:=]\s*\S+)"
)
AttributeValue: TypeAlias = str | int | bool | Decimal | None


def _aware(value: datetime, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be timezone-aware")


def _label(value: str, name: str) -> None:
    if not isinstance(value, str) or _LABEL.fullmatch(value) is None:
        raise ValueError(f"{name} must be a safe label")


def _sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEY_PARTS)


def safe_telemetry_attributes(
    attributes: Mapping[str, object] | None,
) -> tuple[tuple[str, AttributeValue], ...]:
    if attributes is None:
        return ()
    if not isinstance(attributes, Mapping):
        raise ValueError("telemetry attributes must be a mapping")
    safe: list[tuple[str, AttributeValue]] = []
    for key, value in attributes.items():
        _label(key, "telemetry attribute key")
        if _sensitive_key(key):
            raise ValueError(f"sensitive telemetry attribute rejected: {key}")
        if isinstance(value, str):
            if _SENSITIVE_TEXT.search(value) is not None:
                raise ValueError(f"sensitive telemetry attribute rejected: {key}")
            if _LABEL.fullmatch(value) is None:
                raise ValueError(f"telemetry attribute {key} must be a safe label")
        elif type(value) in (int, bool) or value is None:
            pass
        elif isinstance(value, Decimal) and value.is_finite():
            pass
        else:
            raise ValueError(
                "telemetry attributes must be safe strings, integers, booleans, "
                "finite Decimals, or None"
            )
        safe.append((key, value))
    return tuple(sorted(safe, key=lambda item: item[0]))


def _validate_stored_attributes(
    attributes: tuple[tuple[str, AttributeValue], ...],
    owner: str,
) -> None:
    if not isinstance(attributes, tuple):
        raise ValueError(f"{owner} attributes must be an immutable tuple")
    if any(
        not isinstance(item, tuple) or len(item) != 2
        for item in attributes
    ):
        raise ValueError(f"{owner} attributes must contain key/value pairs")
    keys = [item[0] for item in attributes]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{owner} attributes must not contain duplicate keys")
    normalized = safe_telemetry_attributes(dict(attributes))
    if normalized != attributes:
        raise ValueError(f"{owner} attributes must be sorted and safe")


@dataclass(frozen=True)
class Phase2Metric:
    name: str
    category: Phase2TelemetryCategory
    value: Decimal
    unit: Phase2MetricUnit
    observed_at: datetime
    attributes: tuple[tuple[str, AttributeValue], ...] = ()
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise ValueError("metric name must use the arms.phase2 namespace")
        if not isinstance(self.category, Phase2TelemetryCategory):
            raise ValueError("invalid Phase 2 telemetry category")
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise ValueError("metric value must be a finite Decimal")
        if not isinstance(self.unit, Phase2MetricUnit):
            raise ValueError("invalid metric unit")
        _aware(self.observed_at, "observed_at")
        _validate_stored_attributes(self.attributes, "metric")


@dataclass(frozen=True)
class Phase2Event:
    name: str
    category: Phase2TelemetryCategory
    severity: Phase2EventSeverity
    occurred_at: datetime
    attributes: tuple[tuple[str, AttributeValue], ...] = ()
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _NAME.fullmatch(self.name) is None:
            raise ValueError("event name must use the arms.phase2 namespace")
        if not isinstance(self.category, Phase2TelemetryCategory):
            raise ValueError("invalid Phase 2 telemetry category")
        if not isinstance(self.severity, Phase2EventSeverity):
            raise ValueError("invalid event severity")
        _aware(self.occurred_at, "occurred_at")
        _validate_stored_attributes(self.attributes, "event")


Phase2TelemetryRecord: TypeAlias = Phase2Metric | Phase2Event


class Phase2TelemetrySink(Protocol):
    def write(self, records: tuple[Phase2TelemetryRecord, ...]) -> None: ...


@dataclass(frozen=True)
class TelemetryWriteResult:
    status: TelemetryWriteStatus
    attempted_records: int
    recorded_records: int
    canonical_admin_authorized: bool = field(default=False, init=False)
    execution_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.status, TelemetryWriteStatus):
            raise ValueError("invalid telemetry write status")
        for name in ("attempted_records", "recorded_records"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if self.recorded_records > self.attempted_records:
            raise ValueError("recorded telemetry cannot exceed attempted telemetry")
        if self.status == TelemetryWriteStatus.RECORDED and (
            self.recorded_records != self.attempted_records
        ):
            raise ValueError("recorded status requires a complete write")
        if self.status == TelemetryWriteStatus.SINK_UNAVAILABLE and self.recorded_records != 0:
            raise ValueError("failed atomic telemetry write cannot report recorded rows")


class InMemoryPhase2TelemetrySink:
    """Bounded atomic test/local sink with no export or network behavior."""

    def __init__(self, capacity: int = 10_000) -> None:
        if type(capacity) is not int or capacity < 1:
            raise ValueError("telemetry capacity must be a positive integer")
        self._capacity = capacity
        self._records: list[Phase2TelemetryRecord] = []
        self._lock = Lock()

    def write(self, records: tuple[Phase2TelemetryRecord, ...]) -> None:
        if not isinstance(records, tuple) or not records or any(
            not isinstance(item, (Phase2Metric, Phase2Event)) for item in records
        ):
            raise ValueError("telemetry sink requires an immutable nonempty record tuple")
        with self._lock:
            if len(self._records) + len(records) > self._capacity:
                raise RuntimeError("Phase 2 telemetry capacity exhausted")
            self._records.extend(records)

    def snapshot(self) -> tuple[Phase2TelemetryRecord, ...]:
        with self._lock:
            return tuple(self._records)


class Phase2Observability:
    def __init__(
        self,
        sink: Phase2TelemetrySink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sink = sink
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def _now(self) -> datetime:
        observed_at = self._clock()
        _aware(observed_at, "observability clock")
        return observed_at

    def _write(
        self,
        records: tuple[Phase2TelemetryRecord, ...],
    ) -> TelemetryWriteResult:
        try:
            self._sink.write(records)
        except Exception:
            return TelemetryWriteResult(
                TelemetryWriteStatus.SINK_UNAVAILABLE,
                len(records),
                0,
            )
        return TelemetryWriteResult(
            TelemetryWriteStatus.RECORDED,
            len(records),
            len(records),
        )

    def record_rule_evaluation(
        self,
        *,
        outcome: str,
        accepted: bool,
        duration_ms: Decimal,
        firm_id: str,
        program_id: str,
        profile_version: str,
    ) -> TelemetryWriteResult:
        if type(accepted) is not bool:
            raise ValueError("accepted must be boolean")
        now = self._now()
        attributes = safe_telemetry_attributes({
            "accepted": accepted,
            "firm_id": firm_id,
            "outcome": outcome,
            "profile_version": profile_version,
            "program_id": program_id,
        })
        return self._write((
            Phase2Event(
                "arms.phase2.rule_evaluation.completed",
                Phase2TelemetryCategory.RULE_EVALUATION,
                Phase2EventSeverity.INFO if accepted else Phase2EventSeverity.WARNING,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.rule_evaluation.count",
                Phase2TelemetryCategory.RULE_EVALUATION,
                Decimal(1),
                Phase2MetricUnit.COUNT,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.rule_evaluation.duration",
                Phase2TelemetryCategory.RULE_EVALUATION,
                _nonnegative_decimal(duration_ms, "duration_ms"),
                Phase2MetricUnit.MILLISECONDS,
                now,
                attributes,
            ),
        ))

    def record_profile_freshness(
        self,
        *,
        status: str,
        age_seconds: Decimal | None,
        firm_id: str,
        program_id: str,
        profile_version: str,
    ) -> TelemetryWriteResult:
        now = self._now()
        attributes = safe_telemetry_attributes({
            "firm_id": firm_id,
            "profile_version": profile_version,
            "program_id": program_id,
            "status": status,
        })
        records: list[Phase2TelemetryRecord] = [
            Phase2Event(
                "arms.phase2.profile_freshness.observed",
                Phase2TelemetryCategory.PROFILE_FRESHNESS,
                Phase2EventSeverity.INFO,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.profile_freshness.count",
                Phase2TelemetryCategory.PROFILE_FRESHNESS,
                Decimal(1),
                Phase2MetricUnit.COUNT,
                now,
                attributes,
            ),
        ]
        if age_seconds is not None:
            records.append(Phase2Metric(
                "arms.phase2.profile_freshness.age",
                Phase2TelemetryCategory.PROFILE_FRESHNESS,
                _nonnegative_decimal(age_seconds, "age_seconds"),
                Phase2MetricUnit.SECONDS,
                now,
                attributes,
            ))
        return self._write(tuple(records))

    def record_api_call(
        self,
        *,
        operation: str,
        outcome: str,
        duration_ms: Decimal,
    ) -> TelemetryWriteResult:
        return self._record_duration_operation(
            Phase2TelemetryCategory.API_CALL,
            "api_call",
            operation,
            outcome,
            duration_ms,
        )

    def record_notification(
        self,
        *,
        provider: str,
        status: str,
        attempts: int,
        event_type: str,
    ) -> TelemetryWriteResult:
        if type(attempts) is not int or attempts < 0:
            raise ValueError("attempts must be a nonnegative integer")
        now = self._now()
        attributes = safe_telemetry_attributes({
            "event_type": event_type,
            "provider": provider,
            "status": status,
        })
        return self._write((
            Phase2Event(
                "arms.phase2.notification.completed",
                Phase2TelemetryCategory.NOTIFICATION,
                Phase2EventSeverity.INFO,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.notification.count",
                Phase2TelemetryCategory.NOTIFICATION,
                Decimal(1),
                Phase2MetricUnit.COUNT,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.notification.attempts",
                Phase2TelemetryCategory.NOTIFICATION,
                Decimal(attempts),
                Phase2MetricUnit.COUNT,
                now,
                attributes,
            ),
        ))

    def record_account_analytics(
        self,
        *,
        operation: str,
        outcome: str,
        account_count: int,
        missing_data_count: int,
        duration_ms: Decimal,
    ) -> TelemetryWriteResult:
        for name, value in (
            ("account_count", account_count),
            ("missing_data_count", missing_data_count),
        ):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if missing_data_count > account_count:
            raise ValueError("missing account data cannot exceed account count")
        now = self._now()
        attributes = safe_telemetry_attributes({
            "operation": operation,
            "outcome": outcome,
        })
        return self._write((
            Phase2Event(
                "arms.phase2.account_analytics.completed",
                Phase2TelemetryCategory.ACCOUNT_ANALYTICS,
                Phase2EventSeverity.INFO,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.account_analytics.accounts",
                Phase2TelemetryCategory.ACCOUNT_ANALYTICS,
                Decimal(account_count),
                Phase2MetricUnit.COUNT,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.account_analytics.missing_data",
                Phase2TelemetryCategory.ACCOUNT_ANALYTICS,
                Decimal(missing_data_count),
                Phase2MetricUnit.COUNT,
                now,
                attributes,
            ),
            Phase2Metric(
                "arms.phase2.account_analytics.duration",
                Phase2TelemetryCategory.ACCOUNT_ANALYTICS,
                _nonnegative_decimal(duration_ms, "duration_ms"),
                Phase2MetricUnit.MILLISECONDS,
                now,
                attributes,
            ),
        ))

    def _record_duration_operation(
        self,
        category: Phase2TelemetryCategory,
        namespace: str,
        operation: str,
        outcome: str,
        duration_ms: Decimal,
    ) -> TelemetryWriteResult:
        now = self._now()
        attributes = safe_telemetry_attributes({
            "operation": operation,
            "outcome": outcome,
        })
        return self._write((
            Phase2Event(
                f"arms.phase2.{namespace}.completed",
                category,
                Phase2EventSeverity.INFO,
                now,
                attributes,
            ),
            Phase2Metric(
                f"arms.phase2.{namespace}.count",
                category,
                Decimal(1),
                Phase2MetricUnit.COUNT,
                now,
                attributes,
            ),
            Phase2Metric(
                f"arms.phase2.{namespace}.duration",
                category,
                _nonnegative_decimal(duration_ms, "duration_ms"),
                Phase2MetricUnit.MILLISECONDS,
                now,
                attributes,
            ),
        ))


def _nonnegative_decimal(value: Decimal, name: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a nonnegative finite Decimal")
    return value
