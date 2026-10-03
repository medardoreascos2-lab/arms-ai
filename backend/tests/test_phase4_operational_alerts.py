"""R43C tests for side-effect-free operational alert policies."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.phase4.operational_alerts import (
    OperationalAlertEvaluation,
    OperationalAlertInputs,
    OperationalAlertKind,
    OperationalAlertPolicy,
    OperationalAlertState,
    OperationalAlertThresholds,
    OperationalAlertSeverity,
)
from backend.phase4.operational_health import (
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


NOW = datetime(2026, 10, 3, 23, 0, tzinfo=timezone.utc)


def metric_values():
    return {
        OperationalMetricName.API_HEALTH: 1,
        OperationalMetricName.DB_HEALTH: 1,
        OperationalMetricName.WORKER_HEALTH: 1,
        OperationalMetricName.QUEUE_DEPTH: 0,
        OperationalMetricName.OUTBOX_FAILURES: 0,
        OperationalMetricName.SNAPSHOT_LAG_SECONDS: 0,
        OperationalMetricName.EVALUATION_LAG_SECONDS: 0,
        OperationalMetricName.RESEARCH_QUEUE: 0,
        OperationalMetricName.SCHEDULER_HEARTBEAT: 1,
        OperationalMetricName.AUTH_DENIALS: 0,
        OperationalMetricName.MIGRATION_STATE: 1,
    }


def alert_inputs(values=None, **overrides):
    values = values or metric_values()
    snapshot = build_operational_metrics_snapshot(values, observed_at=NOW)
    health = OperationalHealthModel(
        HealthEvaluationPolicy(60, HealthThresholds())
    ).from_metrics(snapshot, evaluated_at=NOW)
    fields = {
        "health": health,
        "metrics": snapshot,
        "evaluated_at": NOW,
        "oldest_queued_at": None,
        "last_successful_backup_at": NOW - timedelta(hours=1),
        "disk_used_percent": Decimal(20),
    }
    fields.update(overrides)
    return OperationalAlertInputs(**fields)


def by_kind(report):
    return {item.kind: item for item in report.evaluations}


def test_all_nine_rules_are_clear_with_current_healthy_evidence():
    report = OperationalAlertPolicy().evaluate(alert_inputs())
    assert tuple(item.kind for item in report.evaluations) == tuple(OperationalAlertKind)
    assert all(item.state is OperationalAlertState.CLEAR for item in report.evaluations)
    assert report.attention_required is False
    assert report.external_delivery_authorized is False
    assert report.execution_authorized is False


def test_database_worker_scheduler_and_migration_health_fire_expected_rules():
    values = metric_values()
    values[OperationalMetricName.DB_HEALTH] = 0
    values[OperationalMetricName.WORKER_HEALTH] = 0
    values[OperationalMetricName.SCHEDULER_HEARTBEAT] = 0
    values[OperationalMetricName.MIGRATION_STATE] = 2
    result = by_kind(OperationalAlertPolicy().evaluate(alert_inputs(values)))
    expected = {
        OperationalAlertKind.DATABASE_UNAVAILABLE,
        OperationalAlertKind.WORKER_STOPPED,
        OperationalAlertKind.SCHEDULER_STOPPED,
        OperationalAlertKind.MIGRATION_FAILURE,
    }
    assert {kind for kind, item in result.items() if item.state is OperationalAlertState.FIRING} == expected


def test_queue_backup_auth_research_and_disk_thresholds_fire():
    values = metric_values()
    values[OperationalMetricName.QUEUE_DEPTH] = 2
    values[OperationalMetricName.AUTH_DENIALS] = 11
    values[OperationalMetricName.RESEARCH_QUEUE] = 101
    inputs = alert_inputs(
        values,
        oldest_queued_at=NOW - timedelta(seconds=301),
        last_successful_backup_at=NOW - timedelta(days=1, seconds=1),
        disk_used_percent=Decimal(91),
    )
    report = OperationalAlertPolicy().evaluate(inputs)
    expected = {
        OperationalAlertKind.QUEUE_STUCK,
        OperationalAlertKind.BACKUP_OVERDUE,
        OperationalAlertKind.AUTH_FAILURE_SPIKE,
        OperationalAlertKind.RESEARCH_RUNAWAY,
        OperationalAlertKind.DISK_PRESSURE,
    }
    assert {item.kind for item in report.firing} == expected
    assert report.attention_required is True


def test_unknown_evidence_requires_attention_and_never_clears_rule():
    values = metric_values()
    values[OperationalMetricName.QUEUE_DEPTH] = 1
    inputs = alert_inputs(
        values,
        oldest_queued_at=None,
        last_successful_backup_at=None,
        disk_used_percent=None,
    )
    report = OperationalAlertPolicy().evaluate(inputs)
    assert {item.kind for item in report.unknown} == {
        OperationalAlertKind.QUEUE_STUCK,
        OperationalAlertKind.BACKUP_OVERDUE,
        OperationalAlertKind.DISK_PRESSURE,
    }
    assert report.attention_required is True


def test_unknown_component_health_never_maps_to_clear():
    inputs = alert_inputs()
    observations = tuple(
        type(item)(
            component=item.component,
            state=HealthState.UNKNOWN if item.component is HealthComponent.DATABASE else item.state,
            source_state=item.source_state,
            code=item.code,
            observed_at=item.observed_at,
            stale=item.stale,
        )
        for item in inputs.health.components
    )
    unknown_health = type(inputs.health)(
        state=HealthState.DEGRADED,
        components=observations,
        evaluated_at=inputs.health.evaluated_at,
        blocking_components=(),
        recovery_components=(),
        unknown_components=(HealthComponent.DATABASE,),
    )
    report = OperationalAlertPolicy().evaluate(
        OperationalAlertInputs(
            unknown_health,
            inputs.metrics,
            NOW,
            inputs.oldest_queued_at,
            inputs.last_successful_backup_at,
            inputs.disk_used_percent,
        )
    )
    assert by_kind(report)[OperationalAlertKind.DATABASE_UNAVAILABLE].state is OperationalAlertState.UNKNOWN


def test_invalid_or_future_operational_evidence_fails_closed():
    with pytest.raises(ValueError, match="cannot exceed"):
        OperationalAlertThresholds(maximum_disk_used_percent=Decimal(101))
    with pytest.raises(ValueError, match="cannot exceed"):
        alert_inputs(disk_used_percent=Decimal(101))
    with pytest.raises(ValueError, match="future"):
        alert_inputs(last_successful_backup_at=NOW + timedelta(seconds=1))


def test_policy_has_no_delivery_or_execution_authority():
    policy = OperationalAlertPolicy()
    report = policy.evaluate(alert_inputs())
    assert policy.external_delivery_authorized is False
    assert policy.production_mutation_authorized is False
    assert all(item.external_delivery_authorized is False for item in report.evaluations)


def test_exported_alert_evaluation_rejects_invalid_direct_construction():
    with pytest.raises(ValueError, match="uppercase identifier"):
        OperationalAlertEvaluation(
            OperationalAlertKind.DISK_PRESSURE,
            OperationalAlertState.FIRING,
            OperationalAlertSeverity.CRITICAL,
            "unsafe code",
        )
    with pytest.raises(ValueError, match="exact Decimal"):
        OperationalAlertEvaluation(
            OperationalAlertKind.DISK_PRESSURE,
            OperationalAlertState.FIRING,
            OperationalAlertSeverity.CRITICAL,
            "THRESHOLD_EXCEEDED",
            91,
            Decimal(90),
        )
