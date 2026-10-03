"""R47C synthetic worker death and lease failover regression."""

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


NOW = datetime(2026, 10, 4, 13, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.current = NOW

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


def worker(store, clock, worker_id, transport, token):
    return OutboxWorker(
        store,
        tenant_id="tenant-failover",
        worker_id=worker_id,
        clock=clock,
        transport=transport,
        config=WorkerConfig(lease_seconds=5),
        token_factory=lambda: token,
    )


def test_dead_worker_lease_expires_and_peer_runs_effect_exactly_once(tmp_path):
    clock = Clock()
    effects = []
    event = OutboxEvent(
        tenant=TenantIdentity("tenant-failover"),
        event_kind="SYNTHETIC_WORK",
        dedupe_key="failover:job:0001",
        payload=DurableStatePayload((("synthetic", True),)),
        created_at=NOW,
        available_at=NOW,
    )
    with Phase3DurableStateStore.create(tmp_path / "failover.sqlite3") as store:
        outbox = DurableOutbox(store)
        outbox.enqueue(event)
        dead = worker(
            store,
            clock,
            "worker-dead",
            lambda item: effects.append(item.event_id),
            "dead-worker-token-0001",
        )
        stale_claim = dead.claim_one()
        assert stale_claim is not None

        peer = worker(
            store,
            clock,
            "worker-peer",
            lambda item: effects.append(item.event_id),
            "peer-worker-token-0001",
        )
        assert peer.process_one().status is WorkerStepStatus.IDLE
        assert effects == []

        clock.advance(6)
        recovered = peer.process_one()
        assert recovered.status is WorkerStepStatus.DELIVERED
        assert recovered.record.status is OutboxStatus.DELIVERED
        assert recovered.record.attempt_count == 2
        assert effects == [event.event_id]

        with pytest.raises(WorkerLeaseLostError, match="no longer owned"):
            dead._finish(stale_claim, delivered=True)
        assert peer.process_one().status is WorkerStepStatus.IDLE
        assert effects == [event.event_id]
        stored = outbox.by_id(
            tenant_id="tenant-failover",
            event_id=event.event_id,
        )
        assert stored.status is OutboxStatus.DELIVERED
        assert stored.lease_owner is None
        assert recovered.execution_authorized is False
        assert recovered.external_delivery_authorized is False
