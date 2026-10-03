"""R42B tests for exclusive leased scheduler supervision."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.phase4.scheduler_supervision import (
    InMemorySchedulerLeaseStore,
    ScheduledJobSpec,
    SchedulerClaimStatus,
    SchedulerJobKind,
    SchedulerLeaseError,
    SchedulerLeaseStore,
    SchedulerRunStatus,
    SchedulerSupervisor,
)


NOW = datetime(2026, 10, 3, 19, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self):
        self.current = NOW

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)


def spec(job_id, kind, *, interval=60, lease=20):
    return ScheduledJobSpec(
        job_id=job_id,
        kind=kind,
        interval_seconds=interval,
        lease_seconds=lease,
        first_due_at=NOW,
    )


def store():
    tokens = iter(f"scheduler-lease-{index:04d}" for index in range(1, 40))
    return InMemorySchedulerLeaseStore(token_factory=lambda: next(tokens))


def scheduler(scheduler_id, shared, clock):
    return SchedulerSupervisor(
        scheduler_id=scheduler_id,
        lease_store=shared,
        clock=clock,
    )


def test_required_job_classes_run_under_exclusive_non_authorizing_claims():
    clock = FakeClock()
    shared = store()
    assert isinstance(shared, SchedulerLeaseStore)
    runtime = scheduler("scheduler-a", shared, clock)
    calls = []
    jobs = (
        spec("research", SchedulerJobKind.RESEARCH_SCHEDULER),
        spec("outbox", SchedulerJobKind.OUTBOX_WORKER),
        spec("maintenance", SchedulerJobKind.MAINTENANCE),
    )
    for item in jobs:
        runtime.register(
            item,
            lambda context, kind=item.kind: calls.append(
                (kind, context.scheduler_id, context.claim.generation)
            ),
        )
    results = runtime.tick()
    assert {result.kind for result in results} == set(SchedulerJobKind)
    assert all(result.status is SchedulerRunStatus.COMPLETED for result in results)
    assert len(calls) == 3
    assert all(result.execution_authorized is False for result in results)
    assert all(result.external_delivery_authorized is False for result in results)
    assert runtime.operating_system_scheduler_modified is False


def test_two_schedulers_cannot_run_the_same_due_generation():
    clock = FakeClock()
    shared = store()
    first = scheduler("scheduler-a", shared, clock)
    second = scheduler("scheduler-b", shared, clock)
    item = spec("outbox", SchedulerJobKind.OUTBOX_WORKER)
    calls = []
    first.register(item, lambda context: calls.append("a"))
    second.register(item, lambda context: calls.append("b"))
    assert first.tick()[0].status is SchedulerRunStatus.COMPLETED
    assert second.tick()[0].status is SchedulerRunStatus.NOT_DUE
    assert calls == ["a"]
    assert shared.state("outbox").generation == 1


def test_unexpired_lease_blocks_peer_and_expired_lease_allows_takeover():
    clock = FakeClock()
    shared = store()
    item = spec("maintenance", SchedulerJobKind.MAINTENANCE, lease=10)
    shared.register(item)
    abandoned = shared.try_claim(
        job_id=item.job_id,
        scheduler_id="scheduler-a",
        now=clock(),
    )
    assert abandoned.status is SchedulerClaimStatus.CLAIMED
    peer = scheduler("scheduler-b", shared, clock)
    calls = []
    peer.register(item, lambda context: calls.append(context.claim.generation))
    assert peer.tick()[0].status is SchedulerRunStatus.LEASE_HELD
    assert calls == []
    clock.advance(10)
    assert peer.tick()[0].status is SchedulerRunStatus.COMPLETED
    assert calls == [2]


def test_job_heartbeat_renews_lease_for_long_running_callback():
    clock = FakeClock()
    shared = store()
    runtime = scheduler("scheduler-a", shared, clock)
    item = spec("research", SchedulerJobKind.RESEARCH_SCHEDULER, lease=5)

    def runner(context):
        clock.advance(4)
        renewed = context.heartbeat()
        assert renewed.expires_at == NOW + timedelta(seconds=9)
        clock.advance(4)

    runtime.register(item, runner)
    result = runtime.tick()[0]
    assert result.status is SchedulerRunStatus.COMPLETED
    assert shared.state(item.job_id).last_completed_at == NOW + timedelta(seconds=8)


def test_completion_after_lease_expiry_is_rejected_and_peer_can_recover():
    clock = FakeClock()
    shared = store()
    first = scheduler("scheduler-a", shared, clock)
    second = scheduler("scheduler-b", shared, clock)
    item = spec("research", SchedulerJobKind.RESEARCH_SCHEDULER, lease=5)
    calls = []

    def stale(context):
        calls.append("stale")
        clock.advance(6)

    first.register(item, stale)
    second.register(item, lambda context: calls.append("recovered"))
    assert first.tick()[0].status is SchedulerRunStatus.LEASE_LOST
    assert second.tick()[0].status is SchedulerRunStatus.COMPLETED
    assert calls == ["stale", "recovered"]
    assert shared.state(item.job_id).generation == 2


def test_failed_job_records_redacted_evidence_and_advances_next_due():
    clock = FakeClock()
    shared = store()
    runtime = scheduler("scheduler-a", shared, clock)
    item = spec("maintenance", SchedulerJobKind.MAINTENANCE, interval=30)

    def failure(_):
        raise RuntimeError("token=fixture-scheduler-secret")

    runtime.register(item, failure)
    result = runtime.tick()[0]
    state = shared.state(item.job_id)
    assert result.status is SchedulerRunStatus.FAILED
    assert "fixture-scheduler-secret" not in repr(result)
    assert state.next_due_at == NOW + timedelta(seconds=30)
    assert state.last_failure == result.failure
    assert runtime.tick()[0].status is SchedulerRunStatus.NOT_DUE


def test_registration_conflicts_and_stale_claim_updates_fail_closed():
    clock = FakeClock()
    shared = store()
    original = spec("outbox", SchedulerJobKind.OUTBOX_WORKER)
    shared.register(original)
    with pytest.raises(SchedulerLeaseError, match="conflicts"):
        shared.register(
            ScheduledJobSpec(
                job_id="outbox",
                kind=SchedulerJobKind.OUTBOX_WORKER,
                interval_seconds=30,
                lease_seconds=20,
                first_due_at=NOW,
            )
        )
    claim = shared.try_claim(
        job_id="outbox", scheduler_id="scheduler-a", now=clock()
    ).claim
    clock.advance(20)
    with pytest.raises(SchedulerLeaseError, match="no longer owned"):
        shared.complete(claim, completed_at=clock())


def test_module_has_no_os_scheduler_process_or_trading_dependency():
    from pathlib import Path
    import backend.phase4.scheduler_supervision as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "subprocess",
        "task scheduler",
        "cron",
        "enterlong",
        "entershort",
        "submit_order",
        "broker_connector",
    )
    assert all(token not in source for token in forbidden)
