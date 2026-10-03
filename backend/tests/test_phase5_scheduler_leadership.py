"""R54B staging rehearsal for exclusive scheduler leadership and takeover."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4.scheduler_supervision import (
    InMemorySchedulerLeaseStore,
    ScheduledJobSpec,
    SchedulerJobKind,
    SchedulerLeaseError,
    SchedulerRunStatus,
    SchedulerSupervisor,
)


NOW = datetime(2026, 10, 4, 2, 0, tzinfo=timezone.utc)


class LocalClock:
    def __init__(self):
        self.current = NOW

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


class SyntheticSchedulerDeath(BaseException):
    """Represents abrupt process loss before completion can clear the lease."""


class LocalIdempotentEffects:
    def __init__(self):
        self.effects = {}
        self.attempts = []

    def apply(self, job_id, scheduled_at, scheduler_id, generation):
        key = (job_id, scheduled_at)
        self.attempts.append((key, scheduler_id, generation))
        self.effects.setdefault(key, (scheduler_id, generation))


def _store():
    tokens = iter(f"phase5-scheduler-lease-{index:04d}" for index in range(1, 20))
    return InMemorySchedulerLeaseStore(token_factory=lambda: next(tokens))


def _scheduler(scheduler_id, store, clock):
    return SchedulerSupervisor(
        scheduler_id=scheduler_id,
        lease_store=store,
        clock=clock,
    )


def _spec(job_id, kind):
    return ScheduledJobSpec(
        job_id=job_id,
        kind=kind,
        interval_seconds=60,
        lease_seconds=10,
        first_due_at=NOW,
    )


@pytest.mark.parametrize(
    ("job_id", "kind"),
    (
        ("phase5_research", SchedulerJobKind.RESEARCH_SCHEDULER),
        ("phase5_outbox", SchedulerJobKind.OUTBOX_WORKER),
    ),
)
def test_peer_waits_for_dead_leader_lease_then_takes_over_once(job_id, kind):
    clock = LocalClock()
    store = _store()
    first = _scheduler("phase5_scheduler_a", store, clock)
    second = _scheduler("phase5_scheduler_b", store, clock)
    item = _spec(job_id, kind)
    abandoned_claims = []
    effects = LocalIdempotentEffects()

    def die_after_claim(context):
        abandoned_claims.append(context.claim)
        raise SyntheticSchedulerDeath("synthetic scheduler process loss")

    def apply_once(context):
        effects.apply(
            context.job.job_id,
            item.first_due_at,
            context.scheduler_id,
            context.claim.generation,
        )

    first.register(item, die_after_claim)
    second.register(item, apply_once)

    with pytest.raises(SyntheticSchedulerDeath, match="process loss"):
        first.tick()

    held = store.state(job_id)
    assert held.lease_owner == "phase5_scheduler_a"
    assert held.generation == 1
    assert second.tick()[0].status is SchedulerRunStatus.LEASE_HELD
    assert effects.effects == {}

    clock.advance(10)
    recovered = second.tick()[0]
    assert recovered.status is SchedulerRunStatus.COMPLETED
    assert recovered.generation == 2
    assert effects.effects == {
        (job_id, NOW): ("phase5_scheduler_b", 2),
    }
    assert len(effects.attempts) == 1

    with pytest.raises(SchedulerLeaseError, match="no longer owned"):
        store.complete(abandoned_claims[0], completed_at=clock())

    assert second.tick()[0].status is SchedulerRunStatus.NOT_DUE
    assert len(effects.attempts) == 1
    assert store.state(job_id).last_completed_at == NOW + timedelta(seconds=10)
    assert recovered.execution_authorized is False
    assert recovered.production_mutation_authorized is False
    assert recovered.external_delivery_authorized is False


def test_two_instances_assign_each_due_job_to_only_one_scheduler():
    clock = LocalClock()
    store = _store()
    first = _scheduler("phase5_scheduler_a", store, clock)
    second = _scheduler("phase5_scheduler_b", store, clock)
    calls = []

    for item in (
        _spec("phase5_research", SchedulerJobKind.RESEARCH_SCHEDULER),
        _spec("phase5_outbox", SchedulerJobKind.OUTBOX_WORKER),
    ):
        first.register(
            item,
            lambda context: calls.append(
                (context.job.job_id, context.scheduler_id, context.claim.generation)
            ),
        )
        second.register(
            item,
            lambda context: calls.append(
                (context.job.job_id, context.scheduler_id, context.claim.generation)
            ),
        )

    first_results = first.tick()
    second_results = second.tick()

    assert all(result.status is SchedulerRunStatus.COMPLETED for result in first_results)
    assert all(result.status is SchedulerRunStatus.NOT_DUE for result in second_results)
    assert calls == [
        ("phase5_outbox", "phase5_scheduler_a", 1),
        ("phase5_research", "phase5_scheduler_a", 1),
    ]
    assert all(store.state(job_id).generation == 1 for job_id in (
        "phase5_research",
        "phase5_outbox",
    ))
    assert first.execution_authorized is False
    assert second.execution_authorized is False
    assert first.production_mutation_authorized is False
    assert second.production_mutation_authorized is False
    assert first.external_delivery_authorized is False
    assert second.external_delivery_authorized is False
