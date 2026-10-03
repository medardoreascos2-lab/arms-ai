"""R43A tests for provider-neutral operational metrics export."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.phase4.operational_metrics import (
    METRIC_UNITS,
    InMemoryMetricsExporter,
    MetricUnit,
    MetricsExporter,
    OperationalMetric,
    OperationalMetricName,
    OperationalMetricsSnapshot,
    build_operational_metrics_snapshot,
    safe_dimensions,
)


NOW = datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc)


def values(changes=None):
    result = {
        OperationalMetricName.API_HEALTH: 1,
        OperationalMetricName.DB_HEALTH: 1,
        OperationalMetricName.WORKER_HEALTH: 1,
        OperationalMetricName.QUEUE_DEPTH: 2,
        OperationalMetricName.OUTBOX_FAILURES: 0,
        OperationalMetricName.SNAPSHOT_LAG_SECONDS: Decimal("0.25"),
        OperationalMetricName.EVALUATION_LAG_SECONDS: Decimal("0.50"),
        OperationalMetricName.RESEARCH_QUEUE: 3,
        OperationalMetricName.SCHEDULER_HEARTBEAT: 1,
        OperationalMetricName.AUTH_DENIALS: 4,
        OperationalMetricName.MIGRATION_STATE: 1,
    }
    result.update(changes or {})
    return result


def snapshot(changes=None):
    return build_operational_metrics_snapshot(
        values(changes),
        observed_at=NOW,
        dimensions={"service": "phase4", "environment": "local_test"},
    )


def test_snapshot_contains_all_required_metrics_in_canonical_order():
    result = snapshot()
    assert tuple(item.name for item in result.metrics) == tuple(OperationalMetricName)
    assert {item.name: item.unit for item in result.metrics} == METRIC_UNITS
    assert len(result.snapshot_id) == 64
    assert all(item.execution_authorized is False for item in result.metrics)
    assert result.execution_authorized is False


def test_missing_extra_lossy_or_invalid_metric_values_fail_closed():
    missing = values()
    missing.pop(OperationalMetricName.API_HEALTH)
    with pytest.raises(ValueError, match="exactly every"):
        build_operational_metrics_snapshot(missing, observed_at=NOW)
    with pytest.raises(ValueError, match="integer or exact Decimal"):
        snapshot({OperationalMetricName.QUEUE_DEPTH: 1.5})
    with pytest.raises(ValueError, match="zero or one"):
        snapshot({OperationalMetricName.API_HEALTH: 2})
    with pytest.raises(ValueError, match="must be integers"):
        snapshot({OperationalMetricName.AUTH_DENIALS: Decimal("1.5")})
    with pytest.raises(ValueError, match="positive"):
        snapshot({OperationalMetricName.MIGRATION_STATE: 0})


def test_sensitive_or_unbounded_dimensions_are_rejected():
    for dimensions in (
        {"token": "fixture-secret"},
        {"service": "authorization=fixture-secret"},
        {"service": "contains spaces"},
    ):
        with pytest.raises(ValueError, match="unsafe"):
            safe_dimensions(dimensions)
    with pytest.raises(ValueError, match="bounded"):
        safe_dimensions({f"key{i}": "value" for i in range(17)})


def test_future_observation_and_wrong_metric_order_are_rejected():
    base = snapshot()
    with pytest.raises(ValueError, match="canonical order"):
        OperationalMetricsSnapshot(tuple(reversed(base.metrics)), NOW)
    future = OperationalMetric(
        OperationalMetricName.API_HEALTH,
        Decimal(1),
        MetricUnit.HEALTH,
        NOW + timedelta(seconds=1),
    )
    metrics = (future,) + base.metrics[1:]
    with pytest.raises(ValueError, match="after snapshot"):
        OperationalMetricsSnapshot(metrics, NOW)


def test_in_memory_export_is_idempotent_bounded_and_provider_neutral():
    exporter = InMemoryMetricsExporter(maximum_snapshots=2)
    assert isinstance(exporter, MetricsExporter)
    first = snapshot()
    exported = exporter.export(first)
    duplicate = exporter.export(first)
    second = build_operational_metrics_snapshot(values(), observed_at=NOW + timedelta(seconds=1))
    third = build_operational_metrics_snapshot(values(), observed_at=NOW + timedelta(seconds=2))
    exporter.export(second)
    exporter.export(third)
    assert exported.exported is True and exported.duplicate is False
    assert duplicate.exported is False and duplicate.duplicate is True
    assert exported.metric_count == len(OperationalMetricName)
    assert tuple(item.snapshot_id for item in exporter.snapshots()) == (
        second.snapshot_id,
        third.snapshot_id,
    )
    assert exporter.external_export_authorized is False


def test_module_has_no_external_collector_network_or_trading_dependency():
    import backend.phase4.operational_metrics as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "requests",
        "httpx",
        "socket",
        "prometheus_client",
        "opentelemetry",
        "broker_connector",
        "enterlong",
        "entershort",
    )
    assert all(token not in source for token in forbidden)
