"""Unified component and aggregate health evaluation for Phase 4."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import re
from types import MappingProxyType

from .operational_metrics import OperationalMetricName, OperationalMetricsSnapshot


_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")


class HealthState(str, Enum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


class HealthComponent(str, Enum):
    API = "API"
    DATABASE = "DATABASE"
    WORKER = "WORKER"
    QUEUE = "QUEUE"
    OUTBOX = "OUTBOX"
    SNAPSHOT_PIPELINE = "SNAPSHOT_PIPELINE"
    EVALUATION_PIPELINE = "EVALUATION_PIPELINE"
    RESEARCH = "RESEARCH"
    SCHEDULER = "SCHEDULER"
    AUTHORIZATION = "AUTHORIZATION"
    MIGRATION = "MIGRATION"


METRIC_COMPONENTS = MappingProxyType({
    OperationalMetricName.API_HEALTH: HealthComponent.API,
    OperationalMetricName.DB_HEALTH: HealthComponent.DATABASE,
    OperationalMetricName.WORKER_HEALTH: HealthComponent.WORKER,
    OperationalMetricName.QUEUE_DEPTH: HealthComponent.QUEUE,
    OperationalMetricName.OUTBOX_FAILURES: HealthComponent.OUTBOX,
    OperationalMetricName.SNAPSHOT_LAG_SECONDS: HealthComponent.SNAPSHOT_PIPELINE,
    OperationalMetricName.EVALUATION_LAG_SECONDS: HealthComponent.EVALUATION_PIPELINE,
    OperationalMetricName.RESEARCH_QUEUE: HealthComponent.RESEARCH,
    OperationalMetricName.SCHEDULER_HEARTBEAT: HealthComponent.SCHEDULER,
    OperationalMetricName.AUTH_DENIALS: HealthComponent.AUTHORIZATION,
    OperationalMetricName.MIGRATION_STATE: HealthComponent.MIGRATION,
})


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _limit(value: object, name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        raise ValueError(f"{name} must be an integer or exact Decimal")
    result = value if isinstance(value, Decimal) else Decimal(value)
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return result


@dataclass(frozen=True)
class HealthThresholds:
    maximum_queue_depth: Decimal = Decimal(1000)
    maximum_outbox_failures: Decimal = Decimal(0)
    maximum_snapshot_lag_seconds: Decimal = Decimal(60)
    maximum_evaluation_lag_seconds: Decimal = Decimal(60)
    maximum_research_queue: Decimal = Decimal(100)
    maximum_auth_denials: Decimal = Decimal(10)
    expected_migration_version: int = 1

    def __post_init__(self) -> None:
        for name in (
            "maximum_queue_depth",
            "maximum_outbox_failures",
            "maximum_snapshot_lag_seconds",
            "maximum_evaluation_lag_seconds",
            "maximum_research_queue",
            "maximum_auth_denials",
        ):
            object.__setattr__(self, name, _limit(getattr(self, name), name))
        if type(self.expected_migration_version) is not int or self.expected_migration_version < 1:
            raise ValueError("expected_migration_version must be positive")


@dataclass(frozen=True)
class HealthEvaluationPolicy:
    maximum_observation_age_seconds: int
    thresholds: HealthThresholds = HealthThresholds()

    def __post_init__(self) -> None:
        if (
            type(self.maximum_observation_age_seconds) is not int
            or self.maximum_observation_age_seconds < 1
        ):
            raise ValueError("maximum_observation_age_seconds must be positive")
        if not isinstance(self.thresholds, HealthThresholds):
            raise ValueError("thresholds must be HealthThresholds")


@dataclass(frozen=True)
class ComponentHealthObservation:
    component: HealthComponent
    state: HealthState
    code: str
    observed_at: datetime
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.component, HealthComponent):
            raise ValueError("component must be a HealthComponent")
        if not isinstance(self.state, HealthState):
            raise ValueError("state must be a HealthState")
        if not isinstance(self.code, str) or _CODE.fullmatch(self.code) is None:
            raise ValueError("code must be an uppercase identifier")
        object.__setattr__(self, "observed_at", _utc(self.observed_at, "observed_at"))


@dataclass(frozen=True)
class ComponentHealth:
    component: HealthComponent
    state: HealthState
    source_state: HealthState
    code: str
    observed_at: datetime
    stale: bool
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


@dataclass(frozen=True)
class OperationalHealthReport:
    state: HealthState
    components: tuple[ComponentHealth, ...]
    evaluated_at: datetime
    blocking_components: tuple[HealthComponent, ...]
    recovery_components: tuple[HealthComponent, ...]
    unknown_components: tuple[HealthComponent, ...]
    execution_authorized: bool = field(default=False, init=False)
    production_mutation_authorized: bool = field(default=False, init=False)


class OperationalHealthModel:
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self, policy: HealthEvaluationPolicy):
        if not isinstance(policy, HealthEvaluationPolicy):
            raise ValueError("policy must be a HealthEvaluationPolicy")
        self.policy = policy

    def evaluate(
        self,
        observations: tuple[ComponentHealthObservation, ...],
        *,
        evaluated_at: datetime,
    ) -> OperationalHealthReport:
        if not isinstance(observations, tuple) or any(
            not isinstance(item, ComponentHealthObservation) for item in observations
        ):
            raise ValueError("observations must be an immutable observation tuple")
        if tuple(item.component for item in observations) != tuple(HealthComponent):
            raise ValueError("observations must cover every component in canonical order")
        now = _utc(evaluated_at, "evaluated_at")
        components = []
        for item in observations:
            if item.observed_at > now:
                raise ValueError("health observation cannot be in the future")
            stale = (
                now - item.observed_at
            ).total_seconds() > self.policy.maximum_observation_age_seconds
            components.append(
                ComponentHealth(
                    component=item.component,
                    state=HealthState.UNKNOWN if stale else item.state,
                    source_state=item.state,
                    code="OBSERVATION_STALE" if stale else item.code,
                    observed_at=item.observed_at,
                    stale=stale,
                )
            )
        states = {item.state for item in components}
        if HealthState.RECOVERY_REQUIRED in states:
            aggregate = HealthState.RECOVERY_REQUIRED
        elif HealthState.BLOCKED in states:
            aggregate = HealthState.BLOCKED
        elif states == {HealthState.UNKNOWN}:
            aggregate = HealthState.UNKNOWN
        elif HealthState.DEGRADED in states or HealthState.UNKNOWN in states:
            aggregate = HealthState.DEGRADED
        else:
            aggregate = HealthState.HEALTHY
        return OperationalHealthReport(
            state=aggregate,
            components=tuple(components),
            evaluated_at=now,
            blocking_components=tuple(
                item.component for item in components if item.state is HealthState.BLOCKED
            ),
            recovery_components=tuple(
                item.component
                for item in components
                if item.state is HealthState.RECOVERY_REQUIRED
            ),
            unknown_components=tuple(
                item.component for item in components if item.state is HealthState.UNKNOWN
            ),
        )

    def from_metrics(
        self,
        snapshot: OperationalMetricsSnapshot,
        *,
        evaluated_at: datetime,
    ) -> OperationalHealthReport:
        if not isinstance(snapshot, OperationalMetricsSnapshot):
            raise ValueError("snapshot must be an OperationalMetricsSnapshot")
        thresholds = self.policy.thresholds
        limit_by_name = {
            OperationalMetricName.QUEUE_DEPTH: thresholds.maximum_queue_depth,
            OperationalMetricName.OUTBOX_FAILURES: thresholds.maximum_outbox_failures,
            OperationalMetricName.SNAPSHOT_LAG_SECONDS: thresholds.maximum_snapshot_lag_seconds,
            OperationalMetricName.EVALUATION_LAG_SECONDS: thresholds.maximum_evaluation_lag_seconds,
            OperationalMetricName.RESEARCH_QUEUE: thresholds.maximum_research_queue,
            OperationalMetricName.AUTH_DENIALS: thresholds.maximum_auth_denials,
        }
        observations = []
        for metric in snapshot.metrics:
            if metric.name in {
                OperationalMetricName.API_HEALTH,
                OperationalMetricName.DB_HEALTH,
                OperationalMetricName.WORKER_HEALTH,
                OperationalMetricName.SCHEDULER_HEARTBEAT,
            }:
                state = HealthState.HEALTHY if metric.value == 1 else HealthState.BLOCKED
                code = "HEALTH_SIGNAL_OK" if state is HealthState.HEALTHY else "HEALTH_SIGNAL_BLOCKED"
            elif metric.name is OperationalMetricName.MIGRATION_STATE:
                expected = Decimal(thresholds.expected_migration_version)
                state = HealthState.HEALTHY if metric.value == expected else HealthState.RECOVERY_REQUIRED
                code = "MIGRATION_CURRENT" if state is HealthState.HEALTHY else "MIGRATION_MISMATCH"
            else:
                state = (
                    HealthState.HEALTHY
                    if metric.value <= limit_by_name[metric.name]
                    else HealthState.DEGRADED
                )
                code = "THRESHOLD_OK" if state is HealthState.HEALTHY else "THRESHOLD_EXCEEDED"
            observations.append(
                ComponentHealthObservation(
                    METRIC_COMPONENTS[metric.name], state, code, metric.observed_at
                )
            )
        return self.evaluate(tuple(observations), evaluated_at=evaluated_at)
