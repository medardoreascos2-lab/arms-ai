"""Pure operational alert policy evaluation with no delivery integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import re

from .operational_health import (
    HealthComponent,
    HealthState,
    OperationalHealthReport,
)
from .operational_metrics import OperationalMetricName, OperationalMetricsSnapshot


_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class OperationalAlertKind(str, Enum):
    DATABASE_UNAVAILABLE = "DATABASE_UNAVAILABLE"
    WORKER_STOPPED = "WORKER_STOPPED"
    SCHEDULER_STOPPED = "SCHEDULER_STOPPED"
    QUEUE_STUCK = "QUEUE_STUCK"
    BACKUP_OVERDUE = "BACKUP_OVERDUE"
    AUTH_FAILURE_SPIKE = "AUTH_FAILURE_SPIKE"
    MIGRATION_FAILURE = "MIGRATION_FAILURE"
    RESEARCH_RUNAWAY = "RESEARCH_RUNAWAY"
    DISK_PRESSURE = "DISK_PRESSURE"


class OperationalAlertState(str, Enum):
    CLEAR = "CLEAR"
    FIRING = "FIRING"
    UNKNOWN = "UNKNOWN"


class OperationalAlertSeverity(str, Enum):
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _nonnegative(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError(f"{name} must be an integer or exact Decimal")
    result = value if isinstance(value, Decimal) else Decimal(value)
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


@dataclass(frozen=True)
class OperationalAlertThresholds:
    maximum_queue_stall_seconds: Decimal = Decimal(300)
    maximum_backup_age_seconds: Decimal = Decimal(86400)
    maximum_auth_failures: Decimal = Decimal(10)
    maximum_research_queue: Decimal = Decimal(100)
    maximum_disk_used_percent: Decimal = Decimal(90)

    def __post_init__(self) -> None:
        for name in (
            "maximum_queue_stall_seconds",
            "maximum_backup_age_seconds",
            "maximum_auth_failures",
            "maximum_research_queue",
            "maximum_disk_used_percent",
        ):
            object.__setattr__(self, name, _nonnegative(getattr(self, name), name))
        if self.maximum_disk_used_percent > 100:
            raise ValueError("maximum_disk_used_percent cannot exceed 100")


@dataclass(frozen=True)
class OperationalAlertInputs:
    health: OperationalHealthReport
    metrics: OperationalMetricsSnapshot
    evaluated_at: datetime
    oldest_queued_at: datetime | None
    last_successful_backup_at: datetime | None
    disk_used_percent: Decimal | None

    def __post_init__(self) -> None:
        if not isinstance(self.health, OperationalHealthReport):
            raise ValueError("health must be an OperationalHealthReport")
        if not isinstance(self.metrics, OperationalMetricsSnapshot):
            raise ValueError("metrics must be an OperationalMetricsSnapshot")
        now = _utc(self.evaluated_at, "evaluated_at")
        object.__setattr__(self, "evaluated_at", now)
        if self.health.evaluated_at > now or self.metrics.captured_at > now:
            raise ValueError("operational evidence cannot be from the future")
        for name in ("oldest_queued_at", "last_successful_backup_at"):
            value = getattr(self, name)
            if value is not None:
                normalized = _utc(value, name)
                if normalized > now:
                    raise ValueError(f"{name} cannot be in the future")
                object.__setattr__(self, name, normalized)
        if self.disk_used_percent is not None:
            used = _nonnegative(self.disk_used_percent, "disk_used_percent")
            if used > 100:
                raise ValueError("disk_used_percent cannot exceed 100")
            object.__setattr__(self, "disk_used_percent", used)


@dataclass(frozen=True)
class OperationalAlertEvaluation:
    kind: OperationalAlertKind
    state: OperationalAlertState
    severity: OperationalAlertSeverity
    code: str
    observed_value: Decimal | None = None
    threshold: Decimal | None = None
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, OperationalAlertKind):
            raise ValueError("kind must be an OperationalAlertKind")
        if not isinstance(self.state, OperationalAlertState):
            raise ValueError("state must be an OperationalAlertState")
        if not isinstance(self.severity, OperationalAlertSeverity):
            raise ValueError("severity must be an OperationalAlertSeverity")
        if not isinstance(self.code, str) or _CODE.fullmatch(self.code) is None:
            raise ValueError("code must be an uppercase identifier")
        for name in ("observed_value", "threshold"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite() or value < 0
            ):
                raise ValueError(f"{name} must be a nonnegative exact Decimal")

    @property
    def requires_attention(self) -> bool:
        return self.state is not OperationalAlertState.CLEAR


@dataclass(frozen=True)
class OperationalAlertReport:
    evaluations: tuple[OperationalAlertEvaluation, ...]
    evaluated_at: datetime
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)
    external_delivery_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.evaluations, tuple) or any(
            not isinstance(item, OperationalAlertEvaluation) for item in self.evaluations
        ):
            raise ValueError("evaluations must be an immutable evaluation tuple")
        expected = tuple(OperationalAlertKind)
        actual = tuple(item.kind for item in self.evaluations)
        if actual != expected:
            raise ValueError("alert evaluations must cover every rule in canonical order")
        object.__setattr__(self, "evaluated_at", _utc(self.evaluated_at, "evaluated_at"))

    @property
    def firing(self) -> tuple[OperationalAlertEvaluation, ...]:
        return tuple(item for item in self.evaluations if item.state is OperationalAlertState.FIRING)

    @property
    def unknown(self) -> tuple[OperationalAlertEvaluation, ...]:
        return tuple(item for item in self.evaluations if item.state is OperationalAlertState.UNKNOWN)

    @property
    def attention_required(self) -> bool:
        return any(item.requires_attention for item in self.evaluations)


class OperationalAlertPolicy:
    """Evaluate alert evidence without emitting or delivering notifications."""

    execution_authorized = False
    production_mutation_authorized = False
    external_delivery_authorized = False

    def __init__(self, thresholds: OperationalAlertThresholds | None = None):
        self.thresholds = thresholds or OperationalAlertThresholds()
        if not isinstance(self.thresholds, OperationalAlertThresholds):
            raise ValueError("thresholds must be OperationalAlertThresholds")

    @staticmethod
    def _health_rule(
        kind: OperationalAlertKind,
        severity: OperationalAlertSeverity,
        component: HealthComponent,
        components: dict[HealthComponent, HealthState],
    ) -> OperationalAlertEvaluation:
        state = components[component]
        if state is HealthState.UNKNOWN:
            return OperationalAlertEvaluation(kind, OperationalAlertState.UNKNOWN, severity, "HEALTH_UNKNOWN")
        if state in (HealthState.BLOCKED, HealthState.RECOVERY_REQUIRED):
            return OperationalAlertEvaluation(kind, OperationalAlertState.FIRING, severity, "HEALTH_BLOCKED")
        return OperationalAlertEvaluation(kind, OperationalAlertState.CLEAR, severity, "HEALTH_CLEAR")

    @staticmethod
    def _threshold_rule(
        kind: OperationalAlertKind,
        severity: OperationalAlertSeverity,
        value: Decimal,
        threshold: Decimal,
    ) -> OperationalAlertEvaluation:
        firing = value > threshold
        return OperationalAlertEvaluation(
            kind,
            OperationalAlertState.FIRING if firing else OperationalAlertState.CLEAR,
            severity,
            "THRESHOLD_EXCEEDED" if firing else "THRESHOLD_CLEAR",
            value,
            threshold,
        )

    def evaluate(self, inputs: OperationalAlertInputs) -> OperationalAlertReport:
        if not isinstance(inputs, OperationalAlertInputs):
            raise ValueError("inputs must be OperationalAlertInputs")
        components = {item.component: item.state for item in inputs.health.components}
        if set(components) != set(HealthComponent):
            raise ValueError("health report must contain every component")
        metrics = {item.name: item.value for item in inputs.metrics.metrics}
        queue_depth = metrics[OperationalMetricName.QUEUE_DEPTH]
        evaluations = [
            self._health_rule(
                OperationalAlertKind.DATABASE_UNAVAILABLE,
                OperationalAlertSeverity.CRITICAL,
                HealthComponent.DATABASE,
                components,
            ),
            self._health_rule(
                OperationalAlertKind.WORKER_STOPPED,
                OperationalAlertSeverity.CRITICAL,
                HealthComponent.WORKER,
                components,
            ),
            self._health_rule(
                OperationalAlertKind.SCHEDULER_STOPPED,
                OperationalAlertSeverity.ERROR,
                HealthComponent.SCHEDULER,
                components,
            ),
        ]
        if queue_depth == 0:
            evaluations.append(OperationalAlertEvaluation(
                OperationalAlertKind.QUEUE_STUCK,
                OperationalAlertState.CLEAR,
                OperationalAlertSeverity.ERROR,
                "QUEUE_EMPTY",
                Decimal(0),
                self.thresholds.maximum_queue_stall_seconds,
            ))
        elif inputs.oldest_queued_at is None:
            evaluations.append(OperationalAlertEvaluation(
                OperationalAlertKind.QUEUE_STUCK,
                OperationalAlertState.UNKNOWN,
                OperationalAlertSeverity.ERROR,
                "QUEUE_AGE_UNKNOWN",
            ))
        else:
            queue_age = Decimal(str((inputs.evaluated_at - inputs.oldest_queued_at).total_seconds()))
            evaluations.append(self._threshold_rule(
                OperationalAlertKind.QUEUE_STUCK,
                OperationalAlertSeverity.ERROR,
                queue_age,
                self.thresholds.maximum_queue_stall_seconds,
            ))
        if inputs.last_successful_backup_at is None:
            evaluations.append(OperationalAlertEvaluation(
                OperationalAlertKind.BACKUP_OVERDUE,
                OperationalAlertState.UNKNOWN,
                OperationalAlertSeverity.CRITICAL,
                "BACKUP_AGE_UNKNOWN",
            ))
        else:
            backup_age = Decimal(str(
                (inputs.evaluated_at - inputs.last_successful_backup_at).total_seconds()
            ))
            evaluations.append(self._threshold_rule(
                OperationalAlertKind.BACKUP_OVERDUE,
                OperationalAlertSeverity.CRITICAL,
                backup_age,
                self.thresholds.maximum_backup_age_seconds,
            ))
        evaluations.append(self._threshold_rule(
            OperationalAlertKind.AUTH_FAILURE_SPIKE,
            OperationalAlertSeverity.ERROR,
            metrics[OperationalMetricName.AUTH_DENIALS],
            self.thresholds.maximum_auth_failures,
        ))
        evaluations.append(self._health_rule(
            OperationalAlertKind.MIGRATION_FAILURE,
            OperationalAlertSeverity.CRITICAL,
            HealthComponent.MIGRATION,
            components,
        ))
        evaluations.append(self._threshold_rule(
            OperationalAlertKind.RESEARCH_RUNAWAY,
            OperationalAlertSeverity.ERROR,
            metrics[OperationalMetricName.RESEARCH_QUEUE],
            self.thresholds.maximum_research_queue,
        ))
        if inputs.disk_used_percent is None:
            evaluations.append(OperationalAlertEvaluation(
                OperationalAlertKind.DISK_PRESSURE,
                OperationalAlertState.UNKNOWN,
                OperationalAlertSeverity.CRITICAL,
                "DISK_USAGE_UNKNOWN",
            ))
        else:
            evaluations.append(self._threshold_rule(
                OperationalAlertKind.DISK_PRESSURE,
                OperationalAlertSeverity.CRITICAL,
                inputs.disk_used_percent,
                self.thresholds.maximum_disk_used_percent,
            ))
        return OperationalAlertReport(tuple(evaluations), inputs.evaluated_at)
