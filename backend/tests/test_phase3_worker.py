"""R32K tests for leased, retrying, isolated outbox work."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    WorkerLeaseLostError,
    WorkerStepStatus,
)


NOW = datetime(2026, 10, 6, 14, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, current=NOW):
        self.current = current

    def __call__(self):
        return self.current

    def advance(self, **delta):
        self.current += timedelta(**delta)


class FakeTransport:
    def __init__(self, failures=()):
        self.failures = list(failures)
        self.events = []

    def __call__(self, item):
        self.events.append(item)
        if self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise failure


def event(index=1, *, tenant_id="tenant-a"):
    return OutboxEvent(
        tenant=TenantIdentity(tenant_id),
        event_kind="NOTIFICATION_QUEUED",
        dedupe_key=f"notification:account-1:drawdown:{index}",
        payload=DurableStatePayload((("account_id", "account-1"),)),
        created_at=NOW,
        available_at=NOW,
    )


def worker(store, clock, transport, *, tenant_id="tenant-a", worker_id="worker-a",
           config=None, token="lease-token-0001"):
    return OutboxWorker(
        store,
        tenant_id=tenant_id,
        worker_id=worker_id,
        clock=clock,
        transport=transport,
        config=config or WorkerConfig(),
        token_factory=lambda: token,
    )


def test_claim_is_transactional_leased_and_attempted(tmp_path):
    clock = FakeClock()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        DurableOutbox(store).enqueue(item)
        claim = worker(store, clock, FakeTransport()).claim_one()

        assert claim is not None
        assert claim.record.event == item
        assert claim.record.status is OutboxStatus.IN_PROGRESS
        assert claim.record.attempt_count == 1
        assert claim.record.lease_owner == "worker-a"
        assert claim.record.lease_token == "lease-token-0001"
        assert claim.record.lease_expires_at == NOW + timedelta(seconds=30)
        assert claim.execution_authorized is False
        assert worker(
            store, clock, FakeTransport(), worker_id="worker-b",
            token="lease-token-0002",
        ).claim_one() is None


def test_success_is_terminal_and_not_delivered_twice(tmp_path):
    clock = FakeClock()
    transport = FakeTransport()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        outbox = DurableOutbox(store)
        outbox.enqueue(item)
        runtime = worker(store, clock, transport)

        first = runtime.process_one()
        second = runtime.process_one()

        assert first.status is WorkerStepStatus.DELIVERED
        assert first.record.status is OutboxStatus.DELIVERED
        assert first.record.delivered_at == NOW
        assert first.record.lease_owner is None
        assert second.status is WorkerStepStatus.IDLE
        assert transport.events == [item]
        assert first.execution_authorized is False
        assert first.external_delivery_authorized is False


def test_failure_schedules_bounded_backoff_and_sanitizes_error(tmp_path):
    clock = FakeClock()
    transport = FakeTransport((RuntimeError("token=top-secret\nfailed"),))
    config = WorkerConfig(initial_backoff_seconds=7, maximum_backoff_seconds=20)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        DurableOutbox(store).enqueue(event())
        runtime = worker(store, clock, transport, config=config)

        result = runtime.process_one()

        assert result.status is WorkerStepStatus.RETRY_SCHEDULED
        assert result.record.status is OutboxStatus.PENDING
        assert result.record.attempt_count == 1
        assert result.record.next_attempt_at == NOW + timedelta(seconds=7)
        assert result.record.last_error == "RuntimeError: token=[REDACTED] failed"
        assert result.record.lease_owner is None
        assert runtime.process_one().status is WorkerStepStatus.IDLE


def test_repeated_failure_reaches_dead_letter_at_attempt_limit(tmp_path):
    clock = FakeClock()
    transport = FakeTransport((RuntimeError("one"), RuntimeError("two")))
    config = WorkerConfig(max_attempts=2, initial_backoff_seconds=3)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        DurableOutbox(store).enqueue(event())
        runtime = worker(store, clock, transport, config=config)

        first = runtime.process_one()
        clock.advance(seconds=3)
        second = runtime.process_one()

        assert first.status is WorkerStepStatus.RETRY_SCHEDULED
        assert second.status is WorkerStepStatus.DEAD_LETTERED
        assert second.record.status is OutboxStatus.DEAD_LETTER
        assert second.record.attempt_count == 2
        assert second.record.last_error == "RuntimeError: two"
        assert runtime.process_one().status is WorkerStepStatus.IDLE


def test_exponential_backoff_is_capped(tmp_path):
    clock = FakeClock()
    transport = FakeTransport((RuntimeError("one"), RuntimeError("two")))
    config = WorkerConfig(
        max_attempts=3, initial_backoff_seconds=3, maximum_backoff_seconds=4,
    )
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        DurableOutbox(store).enqueue(event())
        runtime = worker(store, clock, transport, config=config)

        first = runtime.process_one()
        clock.advance(seconds=3)
        second = runtime.process_one()

        assert first.record.next_attempt_at == NOW + timedelta(seconds=3)
        assert second.record.next_attempt_at == NOW + timedelta(seconds=7)


def test_shutdown_stops_before_claim_or_transport(tmp_path):
    clock = FakeClock()
    transport = FakeTransport()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        outbox = DurableOutbox(store)
        outbox.enqueue(item)
        runtime = worker(store, clock, transport)
        runtime.request_shutdown()

        result = runtime.process_one()

        assert result.status is WorkerStepStatus.SHUTDOWN
        assert transport.events == []
        assert outbox.by_id(tenant_id="tenant-a", event_id=item.event_id).status is OutboxStatus.PENDING


def test_expired_lease_is_recovered_by_another_worker(tmp_path):
    clock = FakeClock()
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        DurableOutbox(store).enqueue(item)
        first = worker(store, clock, FakeTransport(), worker_id="worker-a").claim_one()
        clock.advance(seconds=31)
        transport = FakeTransport()
        second_runtime = worker(
            store, clock, transport, worker_id="worker-b", token="lease-token-0002"
        )

        result = second_runtime.process_one()

        assert first.record.attempt_count == 1
        assert result.status is WorkerStepStatus.DELIVERED
        assert result.record.attempt_count == 2
        assert transport.events == [item]


def test_expired_final_attempt_dead_letters_without_transport(tmp_path):
    clock = FakeClock()
    config = WorkerConfig(max_attempts=1, lease_seconds=10)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        outbox = DurableOutbox(store)
        outbox.enqueue(item)
        worker(store, clock, FakeTransport(), config=config).claim_one()
        clock.advance(seconds=11)
        transport = FakeTransport()
        runtime = worker(
            store, clock, transport, worker_id="worker-b",
            config=config, token="lease-token-0002",
        )

        result = runtime.process_one()
        stored = outbox.by_id(tenant_id="tenant-a", event_id=item.event_id)

        assert result.status is WorkerStepStatus.IDLE
        assert stored.status is OutboxStatus.DEAD_LETTER
        assert stored.last_error == "lease expired at maximum attempts"
        assert transport.events == []


def test_expired_or_superseded_claim_cannot_ack(tmp_path):
    clock = FakeClock()
    config = WorkerConfig(lease_seconds=10)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        DurableOutbox(store).enqueue(event())
        first_runtime = worker(store, clock, FakeTransport(), config=config)
        stale = first_runtime.claim_one()
        clock.advance(seconds=11)
        second_runtime = worker(
            store, clock, FakeTransport(), worker_id="worker-b",
            config=config, token="lease-token-0002",
        )
        current = second_runtime.claim_one()

        with pytest.raises(WorkerLeaseLostError, match="no longer owned"):
            first_runtime._finish(stale, delivered=True)
        completed = second_runtime._finish(current, delivered=True)
        assert completed.status is OutboxStatus.DELIVERED


def test_crash_after_delivery_before_ack_is_redelivered_with_stable_identity(tmp_path):
    clock = FakeClock()
    effects = []
    transport = lambda item: effects.append(item.event_id)
    config = WorkerConfig(lease_seconds=5)
    with Phase3DurableStateStore.create(tmp_path / "phase3.sqlite3") as store:
        item = event()
        DurableOutbox(store).enqueue(item)
        crashed_runtime = worker(store, clock, transport, config=config)
        claim = crashed_runtime.claim_one()
        crashed_runtime.transport(claim.record.event)  # process died before durable ack
        clock.advance(seconds=6)
        recovered = worker(
            store, clock, transport, worker_id="worker-b",
            config=config, token="lease-token-0002",
        ).process_one()

        assert recovered.status is WorkerStepStatus.DELIVERED
        assert effects == [item.event_id, item.event_id]
        assert recovered.record.event.dedupe_key == item.dedupe_key


def test_read_only_store_and_tenant_scope_fail_closed(tmp_path):
    path = tmp_path / "phase3.sqlite3"
    with Phase3DurableStateStore.create(path) as store:
        DurableOutbox(store).enqueue(event(1, tenant_id="tenant-a"))
        DurableOutbox(store).enqueue(event(2, tenant_id="tenant-b"))
        clock = FakeClock()
        transport = FakeTransport()
        result = worker(
            store, clock, transport, tenant_id="tenant-b", worker_id="worker-b"
        ).process_one()
        assert result.record.event.tenant.tenant_id == "tenant-b"
        assert transport.events == [event(2, tenant_id="tenant-b")]
    with Phase3DurableStateStore.open(path, read_only=True) as store:
        with pytest.raises(DurableStoreReadOnlyError):
            worker(store, FakeClock(), FakeTransport()).claim_one()


def test_worker_has_no_network_telegram_broker_or_order_dependency():
    from backend.phase3 import worker as worker_module

    source = Path(worker_module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "requests", "httpx", "telegram", "socket", "broker_connector",
        "backend.execution", "enterlong", "entershort", "submit_order",
    )
    assert all(token not in source for token in forbidden)
    assert OutboxWorker.execution_authorized is False
    assert OutboxWorker.production_mutation_authorized is False
    assert OutboxWorker.external_delivery_authorized is False


@pytest.mark.parametrize(
    "changes",
    (
        {"lease_seconds": 0},
        {"max_attempts": 0},
        {"initial_backoff_seconds": 10, "maximum_backoff_seconds": 5},
    ),
)
def test_invalid_worker_config_is_rejected(changes):
    with pytest.raises(ValueError):
        WorkerConfig(**changes)
