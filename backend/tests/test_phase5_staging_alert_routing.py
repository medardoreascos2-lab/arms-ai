"""R55B staging alert routing rehearsal with a fake local receiver."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.phase4.operational_alerts import (
    OperationalAlertInputs,
    OperationalAlertKind,
    OperationalAlertPolicy,
    OperationalAlertSeverity,
    OperationalAlertState,
)
from backend.phase4.operational_health import (
    HealthEvaluationPolicy,
    HealthThresholds,
    OperationalHealthModel,
)
from backend.phase4.operational_metrics import (
    OperationalMetricName,
    build_operational_metrics_snapshot,
)


NOW = datetime(2026, 10, 4, 4, 0, tzinfo=timezone.utc)


class FakeLocalAlertReceiver:
    provider_id = "phase5_local_test_receiver"
    endpoint = None
    external_delivery_authorized = False
    execution_authorized = False
    production_mutation_authorized = False

    def __init__(self):
        self._received = {}

    def route(self, report):
        for alert in report.firing:
            key = (alert.kind, report.evaluated_at, alert.code)
            self._received.setdefault(key, alert)
        return tuple(self._received.values())

    def received(self):
        return tuple(self._received.values())


def _values(**changes):
    values = {
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
    values.update({OperationalMetricName(name): value for name, value in changes.items()})
    return values


def _report(values=None, **input_changes):
    snapshot = build_operational_metrics_snapshot(
        values or _values(),
        observed_at=NOW,
        dimensions={"environment": "phase5_staging"},
    )
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
    fields.update(input_changes)
    return OperationalAlertPolicy().evaluate(OperationalAlertInputs(**fields))


def test_fake_receiver_routes_all_required_staging_failures_once():
    report = _report(
        _values(
            db_health=0,
            worker_health=0,
            scheduler_heartbeat=0,
            queue_depth=5,
            auth_denials=11,
        ),
        oldest_queued_at=NOW - timedelta(seconds=301),
        last_successful_backup_at=NOW - timedelta(days=1, seconds=1),
        disk_used_percent=Decimal(91),
    )
    receiver = FakeLocalAlertReceiver()

    first_delivery = receiver.route(report)
    repeated_delivery = receiver.route(report)
    by_kind = {alert.kind: alert for alert in first_delivery}

    assert set(by_kind) == {
        OperationalAlertKind.DATABASE_UNAVAILABLE,
        OperationalAlertKind.WORKER_STOPPED,
        OperationalAlertKind.SCHEDULER_STOPPED,
        OperationalAlertKind.BACKUP_OVERDUE,
        OperationalAlertKind.QUEUE_STUCK,
        OperationalAlertKind.DISK_PRESSURE,
        OperationalAlertKind.AUTH_FAILURE_SPIKE,
    }
    assert all(alert.state is OperationalAlertState.FIRING for alert in by_kind.values())
    assert by_kind[OperationalAlertKind.DATABASE_UNAVAILABLE].severity is OperationalAlertSeverity.CRITICAL
    assert by_kind[OperationalAlertKind.WORKER_STOPPED].severity is OperationalAlertSeverity.CRITICAL
    assert by_kind[OperationalAlertKind.SCHEDULER_STOPPED].severity is OperationalAlertSeverity.ERROR
    assert by_kind[OperationalAlertKind.BACKUP_OVERDUE].severity is OperationalAlertSeverity.CRITICAL
    assert by_kind[OperationalAlertKind.QUEUE_STUCK].severity is OperationalAlertSeverity.ERROR
    assert by_kind[OperationalAlertKind.DISK_PRESSURE].severity is OperationalAlertSeverity.CRITICAL
    assert by_kind[OperationalAlertKind.AUTH_FAILURE_SPIKE].severity is OperationalAlertSeverity.ERROR
    assert repeated_delivery == first_delivery
    assert len(receiver.received()) == 7


def test_clear_evidence_does_not_route_alerts_or_create_external_side_effects():
    report = _report()
    receiver = FakeLocalAlertReceiver()

    assert report.firing == ()
    assert receiver.route(report) == ()
    assert receiver.received() == ()
    assert receiver.provider_id == "phase5_local_test_receiver"
    assert receiver.endpoint is None
    assert receiver.external_delivery_authorized is False
    assert receiver.execution_authorized is False
    assert receiver.production_mutation_authorized is False
    assert report.external_delivery_authorized is False
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert all(alert.external_delivery_authorized is False for alert in report.evaluations)
