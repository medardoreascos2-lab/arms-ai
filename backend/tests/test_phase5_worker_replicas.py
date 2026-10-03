"""R58B multi-replica workers over shared durable outbox state."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase3 import (
    DurableOutbox,
    DurableStatePayload,
    OutboxEvent,
    OutboxStatus,
    OutboxWorker,
    Phase3DurableStateStore,
    TenantIdentity,
    WorkerConfig,
    WorkerLeaseLostError,
    WorkerStepStatus,
)
from backend.phase4.retry_operations import DurableRetryOperations, RetryOperationsPolicy


NOW = datetime(2026, 10, 6, 15, 0, tzinfo=timezone.utc)


class SharedClock:
    def __init__(self):
        self.current = NOW

    def __call__(self):
        return self.current

    def advance(self, seconds: int):
        self.current += timedelta(seconds=seconds)


class LocalEffectSink:
    """Idempotent local sink; it cannot perform external delivery."""

    external_delivery_authorized = False

    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.attempts = []
        self.effects = {}

    def __call__(self, event):
        self.attempts.append(event.event_id)
        if self.fail:
            raise RuntimeError("token=synthetic-phase5-worker-failure")
        self.effects.setdefault(event.event_id, event.payload.entries)


def _event(index: int, tenant_id: str = "tenant-a", account_id: str = "account-1"):
    return OutboxEvent(
        tenant=TenantIdentity(tenant_id),
        event_kind="STAGING_NOTIFICATION",
        dedupe_key=f"r58b:{tenant_id}:{account_id}:{index}",
        payload=DurableStatePayload((
            ("account_id", account_id),
            ("simulated", True),
        )),
        created_at=NOW,
        available_at=NOW,
    )


def _worker(store, clock, sink, worker_id, token, *, tenant_id="tenant-a", config=None):
    return OutboxWorker(
        store,
        tenant_id=tenant_id,
        worker_id=worker_id,
        clock=clock,
        transport=sink,
        config=config or WorkerConfig(lease_seconds=5),
        token_factory=lambda: token,
    )


def _database(tmp_path):
    path = tmp_path / "worker-replicas.sqlite3"
    with Phase3DurableStateStore.create(path):
        pass
    return path


def test_expired_owner_is_replaced_and_old_token_cannot_create_duplicate_effect(tmp_path):
    database = _database(tmp_path)
    clock = SharedClock()
    event = _event(1)
    sink = LocalEffectSink()
    config = WorkerConfig(
        lease_seconds=5,
        max_attempts=3,
        initial_backoff_seconds=1,
        maximum_backoff_seconds=1,
    )
    with Phase3DurableStateStore.open(database) as seed:
        DurableOutbox(seed).enqueue(event)
    with (
        Phase3DurableStateStore.open(database) as store_a,
        Phase3DurableStateStore.open(database) as store_b,
    ):
        worker_a = _worker(
            store_a,
            clock,
            sink,
            "phase5-worker-a",
            "phase5-worker-a-token-0001",
            config=config,
        )
        worker_b = _worker(
            store_b,
            clock,
            sink,
            "phase5-worker-b",
            "phase5-worker-b-token-0001",
            config=config,
        )

        abandoned = worker_a.claim_one()
        assert abandoned.record.lease_owner == "phase5-worker-a"
        assert worker_b.claim_one() is None

        clock.advance(6)
        takeover = worker_b.claim_one()
        assert takeover.record.lease_owner == "phase5-worker-b"
        assert takeover.record.attempt_count == 2
        assert takeover.lease_token != abandoned.lease_token

        with pytest.raises(WorkerLeaseLostError, match="no longer owned"):
            worker_a._finish(abandoned, delivered=True)

        sink(takeover.record.event)
        completed = worker_b._finish(takeover, delivered=True)
        assert completed.status is OutboxStatus.DELIVERED
        assert sink.attempts == [event.event_id]
        assert tuple(sink.effects) == (event.event_id,)
        assert worker_a.claim_one() is None
        assert worker_b.claim_one() is None
        assert completed.execution_authorized is False
        assert worker_a.execution_authorized is False
        assert worker_b.production_mutation_authorized is False
        assert sink.external_delivery_authorized is False


def test_replica_retries_are_bounded_and_end_in_one_dead_letter(tmp_path):
    database = _database(tmp_path)
    clock = SharedClock()
    event = _event(2)
    sink = LocalEffectSink(fail=True)
    config = WorkerConfig(
        lease_seconds=5,
        max_attempts=3,
        initial_backoff_seconds=1,
        maximum_backoff_seconds=1,
    )
    with Phase3DurableStateStore.open(database) as seed:
        DurableOutbox(seed).enqueue(event)
    with (
        Phase3DurableStateStore.open(database) as store_a,
        Phase3DurableStateStore.open(database) as store_b,
    ):
        worker_a = _worker(
            store_a,
            clock,
            sink,
            "phase5-worker-a",
            "phase5-worker-a-token-0002",
            config=config,
        )
        worker_b = _worker(
            store_b,
            clock,
            sink,
            "phase5-worker-b",
            "phase5-worker-b-token-0002",
            config=config,
        )

        first = worker_a.process_one()
        clock.advance(1)
        second = worker_b.process_one()
        clock.advance(1)
        third = worker_a.process_one()

        assert first.status is second.status is WorkerStepStatus.RETRY_SCHEDULED
        assert third.status is WorkerStepStatus.DEAD_LETTERED
        assert third.record.status is OutboxStatus.DEAD_LETTER
        assert third.record.attempt_count == config.max_attempts
        assert third.record.last_error == "RuntimeError: token=[REDACTED]"
        assert worker_a.process_one().status is WorkerStepStatus.IDLE
        assert worker_b.process_one().status is WorkerStepStatus.IDLE
        assert sink.attempts == [event.event_id] * config.max_attempts
        assert sink.effects == {}

        dead_letters = DurableRetryOperations(
            store_a,
            RetryOperationsPolicy(maximum_attempts=config.max_attempts),
        ).inspect_dead_letters(tenant_id="tenant-a")
        assert len(dead_letters) == 1
        assert dead_letters[0].event_id == event.event_id
        assert dead_letters[0].retry_eligible is False
        assert dead_letters[0].blocking_reasons == ("MAX_ATTEMPTS_REACHED",)
        assert dead_letters[0].external_delivery_authorized is False


def test_worker_replicas_preserve_tenant_and_account_scope(tmp_path):
    database = _database(tmp_path)
    clock = SharedClock()
    tenant_a = _event(3, "tenant-a", "account-a")
    tenant_b = _event(4, "tenant-b", "account-b")
    sink_a = LocalEffectSink()
    sink_b = LocalEffectSink()
    with Phase3DurableStateStore.open(database) as seed:
        outbox = DurableOutbox(seed)
        outbox.enqueue(tenant_a)
        outbox.enqueue(tenant_b)
    with (
        Phase3DurableStateStore.open(database) as store_a,
        Phase3DurableStateStore.open(database) as store_b,
    ):
        result_a = _worker(
            store_a,
            clock,
            sink_a,
            "phase5-worker-a",
            "phase5-worker-a-token-0003",
            tenant_id="tenant-a",
        ).process_one()
        result_b = _worker(
            store_b,
            clock,
            sink_b,
            "phase5-worker-b",
            "phase5-worker-b-token-0003",
            tenant_id="tenant-b",
        ).process_one()

        assert result_a.status is result_b.status is WorkerStepStatus.DELIVERED
        assert result_a.record.event.tenant.tenant_id == "tenant-a"
        assert result_a.record.event.payload.get("account_id") == "account-a"
        assert result_b.record.event.tenant.tenant_id == "tenant-b"
        assert result_b.record.event.payload.get("account_id") == "account-b"
        assert sink_a.attempts == [tenant_a.event_id]
        assert sink_b.attempts == [tenant_b.event_id]
        assert DurableOutbox(store_a).by_id(
            tenant_id="tenant-b", event_id=tenant_a.event_id
        ) is None
        assert DurableOutbox(store_b).by_id(
            tenant_id="tenant-a", event_id=tenant_b.event_id
        ) is None
