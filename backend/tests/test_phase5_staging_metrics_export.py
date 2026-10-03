"""R55A local staging metrics export rehearsal without an external collector."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.phase4.operational_metrics import (
    InMemoryMetricsExporter,
    OperationalMetricName,
    build_operational_metrics_snapshot,
)


NOW = datetime(2026, 10, 4, 3, 0, tzinfo=timezone.utc)


STAGING_REQUIREMENT_MAP = {
    "db_health": OperationalMetricName.DB_HEALTH,
    "worker_health": OperationalMetricName.WORKER_HEALTH,
    "scheduler_health": OperationalMetricName.SCHEDULER_HEARTBEAT,
    "queue_depth": OperationalMetricName.QUEUE_DEPTH,
    "latency": OperationalMetricName.EVALUATION_LAG_SECONDS,
    "tenant_auth_denials": OperationalMetricName.AUTH_DENIALS,
    "backup_freshness": OperationalMetricName.SNAPSHOT_LAG_SECONDS,
    "research_queue_pressure": OperationalMetricName.RESEARCH_QUEUE,
    "migration_status": OperationalMetricName.MIGRATION_STATE,
}


def _values(**changes):
    values = {
        OperationalMetricName.API_HEALTH: 1,
        OperationalMetricName.DB_HEALTH: 1,
        OperationalMetricName.WORKER_HEALTH: 1,
        OperationalMetricName.QUEUE_DEPTH: 7,
        OperationalMetricName.OUTBOX_FAILURES: 0,
        OperationalMetricName.SNAPSHOT_LAG_SECONDS: Decimal("45.25"),
        OperationalMetricName.EVALUATION_LAG_SECONDS: Decimal("0.125"),
        OperationalMetricName.RESEARCH_QUEUE: 3,
        OperationalMetricName.SCHEDULER_HEARTBEAT: 1,
        OperationalMetricName.AUTH_DENIALS: 2,
        OperationalMetricName.MIGRATION_STATE: 1,
    }
    values.update({OperationalMetricName(name): value for name, value in changes.items()})
    return values


def _snapshot(**changes):
    return build_operational_metrics_snapshot(
        _values(**changes),
        observed_at=NOW,
        captured_at=NOW + timedelta(milliseconds=100),
        dimensions={
            "environment": "phase5_staging",
            "service": "arms_api",
            "tenant_scope": "aggregate",
        },
    )


def test_local_export_contains_every_phase5_staging_signal_with_exact_values():
    snapshot = _snapshot()
    exporter = InMemoryMetricsExporter(maximum_snapshots=4)

    result = exporter.export(snapshot)
    exported = exporter.snapshots()
    by_name = {metric.name: metric for metric in exported[0].metrics}

    assert set(STAGING_REQUIREMENT_MAP.values()) <= set(by_name)
    assert by_name[STAGING_REQUIREMENT_MAP["db_health"]].value == Decimal(1)
    assert by_name[STAGING_REQUIREMENT_MAP["worker_health"]].value == Decimal(1)
    assert by_name[STAGING_REQUIREMENT_MAP["scheduler_health"]].value == Decimal(1)
    assert by_name[STAGING_REQUIREMENT_MAP["queue_depth"]].value == Decimal(7)
    assert by_name[STAGING_REQUIREMENT_MAP["latency"]].value == Decimal("0.125")
    assert by_name[STAGING_REQUIREMENT_MAP["tenant_auth_denials"]].value == Decimal(2)
    assert by_name[STAGING_REQUIREMENT_MAP["backup_freshness"]].value == Decimal("45.25")
    assert by_name[STAGING_REQUIREMENT_MAP["research_queue_pressure"]].value == Decimal(3)
    assert by_name[STAGING_REQUIREMENT_MAP["migration_status"]].value == Decimal(1)
    assert result.exported is True
    assert result.metric_count == len(OperationalMetricName)
    assert exported == (snapshot,)


def test_local_export_preserves_degraded_staging_evidence_and_deduplicates():
    snapshot = _snapshot(
        db_health=0,
        worker_health=0,
        scheduler_heartbeat=0,
        queue_depth=150,
        auth_denials=20,
        research_queue=40,
    )
    exporter = InMemoryMetricsExporter()

    first = exporter.export(snapshot)
    duplicate = exporter.export(snapshot)
    values = {metric.name: metric.value for metric in exporter.snapshots()[0].metrics}

    assert values[OperationalMetricName.DB_HEALTH] == Decimal(0)
    assert values[OperationalMetricName.WORKER_HEALTH] == Decimal(0)
    assert values[OperationalMetricName.SCHEDULER_HEARTBEAT] == Decimal(0)
    assert values[OperationalMetricName.QUEUE_DEPTH] == Decimal(150)
    assert values[OperationalMetricName.AUTH_DENIALS] == Decimal(20)
    assert values[OperationalMetricName.RESEARCH_QUEUE] == Decimal(40)
    assert first.exported is True and first.duplicate is False
    assert duplicate.exported is False and duplicate.duplicate is True
    assert len(exporter.snapshots()) == 1


def test_staging_metrics_remain_local_safe_and_fail_closed():
    exporter = InMemoryMetricsExporter()
    snapshot = _snapshot()
    result = exporter.export(snapshot)

    assert exporter.provider_id == "in_memory"
    assert exporter.external_export_authorized is False
    assert exporter.execution_authorized is False
    assert exporter.production_mutation_authorized is False
    assert result.execution_authorized is False
    assert result.production_mutation_authorized is False
    assert snapshot.execution_authorized is False
    assert snapshot.production_mutation_authorized is False
    assert all(metric.execution_authorized is False for metric in snapshot.metrics)
    assert all(metric.production_mutation_authorized is False for metric in snapshot.metrics)

    incomplete = _values()
    incomplete.pop(OperationalMetricName.DB_HEALTH)
    with pytest.raises(ValueError, match="exactly every"):
        build_operational_metrics_snapshot(incomplete, observed_at=NOW)
    with pytest.raises(ValueError, match="unsafe"):
        build_operational_metrics_snapshot(
            _values(),
            observed_at=NOW,
            dimensions={"authorization": "synthetic-secret"},
        )
