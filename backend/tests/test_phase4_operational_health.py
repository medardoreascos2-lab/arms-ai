"""R43B tests for unified operational health evaluation."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.phase4.operational_health import (
    ComponentHealthObservation,
    HealthComponent,
    HealthEvaluationPolicy,
    HealthState,
    HealthThresholds,
    OperationalHealthModel,
)
from backend.phase4.operational_metrics import (
    OperationalMetricName,
    build_operational_metrics_snapshot,
)


NOW = datetime(2026, 10, 3, 22, 0, tzinfo=timezone.utc)


def observations(state=HealthState.HEALTHY, observed_at=NOW):
    return tuple(
        ComponentHealthObservation(component, state, f"{component.value}_STATE", observed_at)
        for component in HealthComponent
    )


def model(maximum_age=60, thresholds=None):
    return OperationalHealthModel(
        HealthEvaluationPolicy(maximum_age, thresholds or HealthThresholds())
    )


def metric_values():
    return {
        OperationalMetricName.API_HEALTH: 1,
        OperationalMetricName.DB_HEALTH: 1,
        OperationalMetricName.WORKER_HEALTH: 1,
        OperationalMetricName.QUEUE_DEPTH: 0,
        OperationalMetricName.OUTBOX_FAILURES: 0,
        OperationalMetricName.SNAPSHOT_LAG_SECONDS: Decimal("1"),
        OperationalMetricName.EVALUATION_LAG_SECONDS: Decimal("1"),
        OperationalMetricName.RESEARCH_QUEUE: 0,
        OperationalMetricName.SCHEDULER_HEARTBEAT: 1,
        OperationalMetricName.AUTH_DENIALS: 0,
        OperationalMetricName.MIGRATION_STATE: 1,
    }


def test_all_healthy_components_produce_healthy_aggregate():
    report = model().evaluate(observations(), evaluated_at=NOW)
    assert report.state is HealthState.HEALTHY
    assert report.blocking_components == ()
    assert report.recovery_components == ()
    assert report.unknown_components == ()
    assert report.execution_authorized is False


def test_metric_component_mapping_is_immutable():
    from backend.phase4.operational_health import METRIC_COMPONENTS

    with pytest.raises(TypeError):
        METRIC_COMPONENTS[OperationalMetricName.API_HEALTH] = HealthComponent.QUEUE


@pytest.mark.parametrize(
    ("state", "expected"),
    (
        (HealthState.DEGRADED, HealthState.DEGRADED),
        (HealthState.BLOCKED, HealthState.BLOCKED),
        (HealthState.RECOVERY_REQUIRED, HealthState.RECOVERY_REQUIRED),
    ),
)
def test_aggregate_uses_highest_required_response(state, expected):
    items = list(observations())
    items[3] = ComponentHealthObservation(HealthComponent.QUEUE, state, "TEST_STATE", NOW)
    assert model().evaluate(tuple(items), evaluated_at=NOW).state is expected


def test_unknown_is_never_mapped_to_healthy():
    unknown = model().evaluate(observations(HealthState.UNKNOWN), evaluated_at=NOW)
    assert unknown.state is HealthState.UNKNOWN
    mixed = list(observations())
    mixed[0] = ComponentHealthObservation(
        HealthComponent.API, HealthState.UNKNOWN, "NO_DATA", NOW
    )
    report = model().evaluate(tuple(mixed), evaluated_at=NOW)
    assert report.state is HealthState.DEGRADED
    assert report.unknown_components == (HealthComponent.API,)


def test_stale_observations_become_unknown_without_changing_source_state():
    report = model(maximum_age=10).evaluate(
        observations(HealthState.HEALTHY, NOW - timedelta(seconds=11)),
        evaluated_at=NOW,
    )
    assert report.state is HealthState.UNKNOWN
    assert all(item.state is HealthState.UNKNOWN for item in report.components)
    assert all(item.source_state is HealthState.HEALTHY for item in report.components)
    assert all(item.stale for item in report.components)


def test_metric_thresholds_map_to_component_and_aggregate_health():
    values = metric_values()
    values[OperationalMetricName.QUEUE_DEPTH] = 11
    values[OperationalMetricName.DB_HEALTH] = 0
    snapshot = build_operational_metrics_snapshot(values, observed_at=NOW)
    report = model(
        thresholds=HealthThresholds(maximum_queue_depth=10)
    ).from_metrics(snapshot, evaluated_at=NOW)
    assert report.state is HealthState.BLOCKED
    states = {item.component: item.state for item in report.components}
    assert states[HealthComponent.QUEUE] is HealthState.DEGRADED
    assert states[HealthComponent.DATABASE] is HealthState.BLOCKED


def test_migration_mismatch_requires_recovery():
    values = metric_values()
    values[OperationalMetricName.MIGRATION_STATE] = 2
    report = model().from_metrics(
        build_operational_metrics_snapshot(values, observed_at=NOW),
        evaluated_at=NOW,
    )
    assert report.state is HealthState.RECOVERY_REQUIRED
    assert report.recovery_components == (HealthComponent.MIGRATION,)


def test_missing_reordered_or_future_observations_fail_closed():
    with pytest.raises(ValueError, match="every component"):
        model().evaluate(observations()[:-1], evaluated_at=NOW)
    with pytest.raises(ValueError, match="canonical order"):
        model().evaluate(tuple(reversed(observations())), evaluated_at=NOW)
    future = list(observations())
    future[0] = ComponentHealthObservation(
        HealthComponent.API, HealthState.HEALTHY, "API_STATE", NOW + timedelta(seconds=1)
    )
    with pytest.raises(ValueError, match="future"):
        model().evaluate(tuple(future), evaluated_at=NOW)
