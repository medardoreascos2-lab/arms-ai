"""R59C staging pressure tests for bounded research and reserved operations."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Barrier, Lock
import time

from backend.phase4 import (
    InMemorySchedulerLeaseStore,
    IsolatedLoadHarness,
    LoadDomain,
    LoadHarnessConfig,
    LoadOperation,
    ScheduledJobSpec,
    SchedulerJobKind,
    SchedulerRunStatus,
    SchedulerSupervisor,
)
from backend.research import (
    ResearchJobKind,
    ResearchJobQueue,
    ResearchJobRequest,
    ResearchSchedulerMode,
    ResearchResourceGovernor,
    ResearchResourceLimits,
    ResearchResourceRequest,
    ResearchResourceUsage,
)


NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def _resource_request(index: int) -> ResearchResourceRequest:
    return ResearchResourceRequest(
        job_id=f"pressure-{index:03d}",
        requested_cpu_percent=Decimal("20"),
        requested_memory_bytes=2_000,
        requested_disk_bytes=4_000,
        requested_datasets=1,
        requested_experiments=1,
        maximum_runtime_seconds=900,
    )


def _queue_request(index: int) -> ResearchJobRequest:
    return ResearchJobRequest(
        strategy_id=f"pressure-strategy-{index:03d}",
        kind=ResearchJobKind.STRESS,
        evidence_ids=(f"synthetic-dataset-{index:03d}",),
        eligible_modes=(ResearchSchedulerMode.WEEKEND_RESEARCH,),
        estimated_cpu_percent=Decimal("20"),
        estimated_storage_bytes=4_000,
        priority=100 - index,
    )


def test_resource_governor_throttles_research_and_preserves_operational_reserves():
    total_cpu = Decimal("100")
    total_memory = 10_000
    total_disk = 20_000
    limits = ResearchResourceLimits(
        maximum_cpu_percent=Decimal("60"),
        maximum_concurrent_jobs=3,
        maximum_memory_bytes=6_000,
        maximum_disk_bytes=12_000,
        maximum_datasets=3,
        maximum_experiments=3,
        maximum_runtime_seconds_per_job=900,
    )
    usage = ResearchResourceUsage(0, Decimal("0"), 0, 0, 0, 0)
    queue = ResearchJobQueue()
    admitted = []
    denied = []

    for index in range(20):
        decision = ResearchResourceGovernor().evaluate(
            _resource_request(index), usage, limits
        )
        if decision.accepted:
            admitted.append(decision)
            queue.enqueue(_queue_request(index))
            usage = ResearchResourceUsage(
                decision.projected_concurrent_jobs,
                decision.projected_cpu_percent,
                decision.projected_memory_bytes,
                decision.projected_disk_bytes,
                decision.projected_datasets,
                decision.projected_experiments,
            )
        else:
            denied.append(decision)

    assert len(admitted) == len(queue.list()) == 3
    assert len(denied) == 17
    assert total_cpu - usage.reserved_cpu_percent == Decimal("40")
    assert total_memory - usage.memory_used_bytes == 4_000
    assert total_disk - usage.disk_used_bytes == 8_000
    assert all(item.execution_authorized is False for item in denied)
    assert all(item.queue_mutation_authorized is False for item in denied)
    assert all({
        "CONCURRENCY_LIMIT_REACHED",
        "CPU_LIMIT_REACHED",
        "MEMORY_LIMIT_REACHED",
        "DISK_LIMIT_REACHED",
    }.issubset(item.blocking_reasons) for item in denied)


def test_worker_pool_keeps_operational_capacity_and_queue_bounded_under_pressure():
    lock = Lock()
    rendezvous = Barrier(4)
    active_research = 0
    maximum_active_research = 0
    operational_completed = 0

    def research_work():
        nonlocal active_research, maximum_active_research
        with lock:
            active_research += 1
            maximum_active_research = max(maximum_active_research, active_research)
        rendezvous.wait(timeout=2)
        time.sleep(0.01)
        with lock:
            active_research -= 1

    def operational_work(wait_for_pressure: bool = False):
        nonlocal operational_completed
        if wait_for_pressure:
            rendezvous.wait(timeout=2)
        with lock:
            operational_completed += 1

    operations = [
        LoadOperation(f"research-{index}", LoadDomain.RESEARCH_QUEUE, research_work)
        for index in range(2)
    ]
    operations.extend(
        LoadOperation(
            f"operational-{index:03d}",
            LoadDomain.OUTBOX if index % 2 else LoadDomain.SNAPSHOT_INGESTION,
            lambda wait=index < 2: operational_work(wait),
        )
        for index in range(50)
    )
    report = IsolatedLoadHarness(
        LoadHarnessConfig(maximum_workers=4, maximum_in_flight=8)
    ).run(tuple(operations))

    assert all(sample.succeeded for sample in report.samples)
    assert maximum_active_research == 2
    assert operational_completed == 50
    assert report.maximum_queue_depth <= 8
    assert report.execution_authorized is False
    assert report.live_trading_authorized is False


def test_scheduler_pressure_failure_does_not_starve_operational_jobs():
    store = InMemorySchedulerLeaseStore(
        token_factory=iter(
            f"phase5-r59c-token-{index:04d}" for index in range(10)
        ).__next__
    )
    scheduler = SchedulerSupervisor(
        scheduler_id="phase5-r59c-scheduler",
        lease_store=store,
        clock=lambda: NOW,
    )
    effects = []

    def research_failure(_context):
        raise RuntimeError("synthetic research pressure limit")

    for job_id, kind, runner in (
        ("a_research", SchedulerJobKind.RESEARCH_SCHEDULER, research_failure),
        ("b_maintenance", SchedulerJobKind.MAINTENANCE, lambda _: effects.append("maintenance")),
        ("c_outbox", SchedulerJobKind.OUTBOX_WORKER, lambda _: effects.append("outbox")),
    ):
        scheduler.register(
            ScheduledJobSpec(job_id, kind, 60, 10, NOW - timedelta(seconds=1)),
            runner,
        )

    results = scheduler.tick()

    assert tuple(item.status for item in results) == (
        SchedulerRunStatus.FAILED,
        SchedulerRunStatus.COMPLETED,
        SchedulerRunStatus.COMPLETED,
    )
    assert effects == ["maintenance", "outbox"]
    assert all(item.execution_authorized is False for item in results)
    assert all(item.production_mutation_authorized is False for item in results)
    assert all(item.external_delivery_authorized is False for item in results)


def test_hard_limits_fail_closed_without_queue_or_execution_side_effects():
    limits = ResearchResourceLimits(
        Decimal("60"), 3, 6_000, 12_000, 3, 3, 900
    )
    usage = ResearchResourceUsage(3, Decimal("60"), 6_000, 12_000, 3, 3)
    queue = ResearchJobQueue()
    before = usage

    decisions = tuple(
        ResearchResourceGovernor().evaluate(_resource_request(index), usage, limits)
        for index in range(100)
    )

    assert all(decision.accepted is False for decision in decisions)
    assert all(decision.execution_authorized is False for decision in decisions)
    assert all(decision.queue_mutation_authorized is False for decision in decisions)
    assert usage == before
    assert queue.list() == ()
