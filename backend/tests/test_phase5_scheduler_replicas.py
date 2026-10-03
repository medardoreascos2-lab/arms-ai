"""R58C multi-replica scheduler leadership and isolation tests."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4.scheduler_supervision import (
    InMemorySchedulerLeaseStore,
    ScheduledJobSpec,
    SchedulerClaimStatus,
    SchedulerJobKind,
    SchedulerLeaseError,
    SchedulerRunStatus,
    SchedulerSupervisor,
)


NOW = datetime(2026, 10, 6, 16, 0, tzinfo=timezone.utc)


class SharedClock:
    def __init__(self):
        self.current = NOW

    def __call__(self):
        return self.current

    def advance(self, seconds: int):
        self.current += timedelta(seconds=seconds)


class LocalOnceEffects:
    execution_authorized = False
    external_delivery_authorized = False

    def __init__(self):
        self.attempts = []
        self.effects = {}

    def apply(self, context):
        key = (context.job.kind, context.job.first_due_at)
        self.attempts.append((key, context.scheduler_id, context.claim.generation))
        self.effects.setdefault(key, (context.scheduler_id, context.claim.generation))


def _store():
    tokens = iter(f"phase5-r58c-scheduler-token-{index:04d}" for index in range(1, 50))
    return InMemorySchedulerLeaseStore(token_factory=lambda: next(tokens))


def _scheduler(scheduler_id, store, clock):
    return SchedulerSupervisor(
        scheduler_id=scheduler_id,
        lease_store=store,
        clock=clock,
    )


def _job(job_id, kind, *, lease=10, interval=60):
    return ScheduledJobSpec(
        job_id=job_id,
        kind=kind,
        interval_seconds=interval,
        lease_seconds=lease,
        first_due_at=NOW,
    )


def test_single_leader_renews_lease_while_peer_remains_blocked():
    clock = SharedClock()
    store = _store()
    first = _scheduler("phase5-scheduler-a", store, clock)
    second = _scheduler("phase5-scheduler-b", store, clock)
    job = _job("phase5-maintenance", SchedulerJobKind.MAINTENANCE, lease=5)
    effects = LocalOnceEffects()
    peer_results = []

    def long_running(context):
        clock.advance(4)
        renewed = context.heartbeat()
        assert renewed.generation == 1
        assert renewed.expires_at == NOW + timedelta(seconds=9)
        clock.advance(4)
        peer_results.extend(second.tick())
        effects.apply(context)

    first.register(job, long_running)
    second.register(job, effects.apply)

    completed = first.tick()[0]
    assert completed.status is SchedulerRunStatus.COMPLETED
    assert completed.generation == 1
    assert len(peer_results) == 1
    assert peer_results[0].status is SchedulerRunStatus.LEASE_HELD
    assert effects.attempts == [
        ((SchedulerJobKind.MAINTENANCE, NOW), "phase5-scheduler-a", 1)
    ]
    assert len(effects.effects) == 1
    assert store.state(job.job_id).last_completed_at == NOW + timedelta(seconds=8)
    assert first.execution_authorized is False
    assert second.production_mutation_authorized is False
    assert second.external_delivery_authorized is False


def test_leader_death_expires_into_safe_takeover_without_cross_job_blocking():
    clock = SharedClock()
    store = _store()
    effects = LocalOnceEffects()
    jobs = (
        _job("phase5-maintenance", SchedulerJobKind.MAINTENANCE),
        _job("phase5-outbox", SchedulerJobKind.OUTBOX_WORKER),
        _job("phase5-research", SchedulerJobKind.RESEARCH_SCHEDULER),
    )
    for job in jobs:
        store.register(job)

    abandoned = store.try_claim(
        job_id="phase5-research",
        scheduler_id="phase5-scheduler-a",
        now=clock(),
    )
    assert abandoned.status is SchedulerClaimStatus.CLAIMED
    assert abandoned.claim.generation == 1

    survivor = _scheduler("phase5-scheduler-b", store, clock)
    for job in jobs:
        survivor.register(job, effects.apply)

    before_expiry = {result.job_id: result for result in survivor.tick()}
    assert before_expiry["phase5-maintenance"].status is SchedulerRunStatus.COMPLETED
    assert before_expiry["phase5-outbox"].status is SchedulerRunStatus.COMPLETED
    assert before_expiry["phase5-research"].status is SchedulerRunStatus.LEASE_HELD
    assert set(effects.effects) == {
        (SchedulerJobKind.MAINTENANCE, NOW),
        (SchedulerJobKind.OUTBOX_WORKER, NOW),
    }

    clock.advance(10)
    after_expiry = {result.job_id: result for result in survivor.tick()}
    assert after_expiry["phase5-research"].status is SchedulerRunStatus.COMPLETED
    assert after_expiry["phase5-research"].generation == 2
    assert after_expiry["phase5-maintenance"].status is SchedulerRunStatus.NOT_DUE
    assert after_expiry["phase5-outbox"].status is SchedulerRunStatus.NOT_DUE

    with pytest.raises(SchedulerLeaseError, match="no longer owned"):
        store.complete(abandoned.claim, completed_at=clock())

    assert len(effects.effects) == 3
    assert len(effects.attempts) == 3
    assert effects.effects[(SchedulerJobKind.RESEARCH_SCHEDULER, NOW)] == (
        "phase5-scheduler-b",
        2,
    )
    assert store.state("phase5-research").generation == 2
    assert store.state("phase5-maintenance").generation == 1
    assert store.state("phase5-outbox").generation == 1
    assert effects.execution_authorized is False
    assert effects.external_delivery_authorized is False
