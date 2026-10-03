"""R42C tests for durable dead-letter inspection and retry containment."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase3 import (
    DurableOutbox,
    DurableStatePayload,
    DurableStoreReadOnlyError,
    OutboxEvent,
    OutboxStatus,
    OutboxWorker,
    Phase3DurableStateStore,
    TenantIdentity,
    WorkerConfig,
    WorkerStepStatus,
)
from backend.phase4.retry_operations import (
    DurableRetryOperations,
    RetryAuthorizationDecision,
    RetryOperationsPolicy,
)


NOW = datetime(2026, 10, 3, 20, 0, tzinfo=timezone.utc)


def event(index=1, tenant_id="tenant-a"):
    return OutboxEvent(
        tenant=TenantIdentity(tenant_id),
        event_kind="NOTIFICATION_QUEUED",
        dedupe_key=f"notification:retry:{index}",
        payload=DurableStatePayload((("safe_reason", "test"),)),
        created_at=NOW,
        available_at=NOW,
    )


def dead_letter(store, item, *, error="token=fixture-retry-secret"):
    DurableOutbox(store).enqueue(item)
    worker = OutboxWorker(
        store,
        tenant_id=item.tenant.tenant_id,
        worker_id="worker-a",
        clock=lambda: NOW,
        transport=lambda _: (_ for _ in ()).throw(RuntimeError(error)),
        config=WorkerConfig(max_attempts=1),
        token_factory=lambda: "lease-token-retry-0001",
    )
    result = worker.process_one()
    assert result.status is WorkerStepStatus.DEAD_LETTERED
    return result.record


def approved(value=True):
    return RetryAuthorizationDecision(
        accepted=value,
        principal_id="operator-a",
        request_id="request-42c-1",
        reason="AUTHORIZED" if value else "DENIED",
    )


def operations(store, *, maximum_attempts=3, delay=5):
    return DurableRetryOperations(
        store,
        RetryOperationsPolicy(
            maximum_attempts=maximum_attempts,
            retry_delay_seconds=delay,
        ),
    )


def row_state(store, tenant_id, event_id):
    return store._connection.execute(
        """SELECT status, attempt_count, next_attempt_at, last_error, updated_at,
                  lease_owner, lease_token, lease_expires_at, delivered_at
           FROM phase3_outbox WHERE tenant_id = ? AND event_id = ?""",
        (tenant_id, event_id),
    ).fetchone()


def test_dead_letter_inspection_is_tenant_scoped_sanitized_and_read_only(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        first = dead_letter(store, event(1, "tenant-a"))
        dead_letter(store, event(2, "tenant-b"))
        before = store._connection.total_changes
        inspected = operations(store).inspect_dead_letters(tenant_id="tenant-a")
        assert len(inspected) == 1
        assert inspected[0].event_id == first.event.event_id
        assert inspected[0].retry_eligible is True
        assert inspected[0].quarantined is False
        assert "fixture-retry-secret" not in repr(inspected)
        assert inspected[0].execution_authorized is False
        assert store._connection.total_changes == before


def test_denied_retry_has_zero_database_side_effects(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        record = dead_letter(store, event())
        before_row = row_state(store, "tenant-a", record.event.event_id)
        before_changes = store._connection.total_changes
        result = operations(store).schedule_retry(
            tenant_id="tenant-a",
            event_id=record.event.event_id,
            reason="operator request",
            now=NOW + timedelta(seconds=1),
            authorization=approved(False),
        )
        assert result.accepted is False
        assert result.changed is False
        assert result.blocking_reasons == ("UNAUTHORIZED",)
        assert result.record is None
        assert row_state(store, "tenant-a", record.event.event_id) == before_row
        assert store._connection.total_changes == before_changes


def test_quarantine_persists_sanitized_evidence_and_blocks_retry(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        record = dead_letter(store, event())
        runtime = operations(store)
        quarantined = runtime.quarantine(
            tenant_id="tenant-a",
            event_id=record.event.event_id,
            reason="webhook=fixture-webhook-secret permanent failure",
            now=NOW + timedelta(seconds=1),
            authorization=approved(),
        )
        assert quarantined.accepted is True
        assert quarantined.record.status is OutboxStatus.DEAD_LETTER
        assert quarantined.record.last_error.startswith("[QUARANTINED]")
        assert "fixture-webhook-secret" not in quarantined.record.last_error
        inspection = runtime.inspect_dead_letters(tenant_id="tenant-a")[0]
        assert inspection.quarantined is True
        assert inspection.retry_eligible is False
        before = row_state(store, "tenant-a", record.event.event_id)
        blocked = runtime.schedule_retry(
            tenant_id="tenant-a",
            event_id=record.event.event_id,
            reason="retry",
            now=NOW + timedelta(seconds=2),
            authorization=approved(),
        )
        assert blocked.blocking_reasons == ("QUARANTINED",)
        assert row_state(store, "tenant-a", record.event.event_id) == before


def test_explicit_quarantine_release_schedules_retry_without_resetting_attempts(tmp_path):
    delivered = []
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        record = dead_letter(store, event())
        runtime = operations(store, delay=7)
        runtime.quarantine(
            tenant_id="tenant-a",
            event_id=record.event.event_id,
            reason="manual hold",
            now=NOW + timedelta(seconds=1),
            authorization=approved(),
        )
        result = runtime.schedule_retry(
            tenant_id="tenant-a",
            event_id=record.event.event_id,
            reason="authorization=fixture-auth-secret reviewed",
            now=NOW + timedelta(seconds=2),
            authorization=approved(),
            release_quarantine=True,
        )
        assert result.accepted is True
        assert result.record.status is OutboxStatus.PENDING
        assert result.record.attempt_count == 1
        assert result.record.next_attempt_at == NOW + timedelta(seconds=9)
        assert "fixture-auth-secret" not in result.record.last_error
        assert delivered == []
        assert result.external_delivery_authorized is False


def test_max_attempts_not_dead_letter_and_wrong_tenant_reject_without_mutation(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        record = dead_letter(store, event())
        limited = operations(store, maximum_attempts=1)
        before = row_state(store, "tenant-a", record.event.event_id)
        before_changes = store._connection.total_changes
        maxed = limited.schedule_retry(
            tenant_id="tenant-a",
            event_id=record.event.event_id,
            reason="retry",
            now=NOW + timedelta(seconds=1),
            authorization=approved(),
        )
        assert maxed.blocking_reasons == ("MAX_ATTEMPTS_REACHED",)
        missing = limited.schedule_retry(
            tenant_id="tenant-b",
            event_id=record.event.event_id,
            reason="retry",
            now=NOW + timedelta(seconds=1),
            authorization=approved(),
        )
        assert missing.blocking_reasons == ("NOT_FOUND",)
        assert row_state(store, "tenant-a", record.event.event_id) == before
        assert store._connection.total_changes == before_changes

        pending = event(2)
        DurableOutbox(store).enqueue(pending)
        not_dead = limited.quarantine(
            tenant_id="tenant-a",
            event_id=pending.event_id,
            reason="hold",
            now=NOW + timedelta(seconds=1),
            authorization=approved(),
        )
        assert not_dead.blocking_reasons == ("NOT_DEAD_LETTER",)


def test_operation_timestamp_cannot_move_durable_state_backward(tmp_path):
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        record = dead_letter(store, event())
        before = row_state(store, "tenant-a", record.event.event_id)
        before_changes = store._connection.total_changes
        result = operations(store).schedule_retry(
            tenant_id="tenant-a",
            event_id=record.event.event_id,
            reason="retry",
            now=NOW - timedelta(seconds=1),
            authorization=approved(),
        )
        assert result.blocking_reasons == ("TIME_REGRESSION",)
        assert row_state(store, "tenant-a", record.event.event_id) == before
        assert store._connection.total_changes == before_changes


def test_read_only_store_allows_inspection_and_blocks_mutation(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        record = dead_letter(store, event())
    with Phase3DurableStateStore.open(path, read_only=True) as store:
        runtime = operations(store)
        assert len(runtime.inspect_dead_letters(tenant_id="tenant-a")) == 1
        with pytest.raises(DurableStoreReadOnlyError, match="read-only"):
            runtime.schedule_retry(
                tenant_id="tenant-a",
                event_id=record.event.event_id,
                reason="retry",
                now=NOW + timedelta(seconds=1),
                authorization=approved(),
            )


def test_module_has_no_transport_network_or_execution_dependency():
    from pathlib import Path
    import backend.phase4.retry_operations as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "requests",
        "httpx",
        "socket",
        "telegram",
        "broker_connector",
        "enterlong",
        "entershort",
        "submit_order",
    )
    assert all(token not in source for token in forbidden)
    assert DurableRetryOperations.external_delivery_authorized is False
