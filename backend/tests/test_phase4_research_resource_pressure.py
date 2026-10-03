"""R47E synthetic research pressure tests with protected operational capacity."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backend.research.research_scheduler import (
    ResearchJobKind,
    ResearchJobQueue,
    ResearchJobRequest,
    ResearchSchedulerContext,
    ResearchSchedulerLimits,
    ResearchSchedulerMode,
    WeekendResearchScheduler,
)
from backend.research.resource_governor import (
    ResearchResourceGovernor,
    ResearchResourceLimits,
    ResearchResourceRequest,
    ResearchResourceUsage,
)


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
TOTAL_CPU = Decimal("100")
TOTAL_MEMORY = 10_000
TOTAL_DISK = 20_000
OPERATIONAL_CPU_RESERVE = Decimal("40")
OPERATIONAL_MEMORY_RESERVE = 4_000
OPERATIONAL_DISK_RESERVE = 8_000


def _scheduler_job(index):
    return ResearchJobRequest(
        strategy_id=f"challenger-{index:02d}",
        kind=ResearchJobKind.BACKTEST,
        evidence_ids=(f"dataset-{index:02d}", "weekend-window"),
        eligible_modes=(ResearchSchedulerMode.WEEKEND_RESEARCH,),
        estimated_cpu_percent=Decimal("15"),
        estimated_storage_bytes=300,
        priority=100 - index,
    )


def _resource_request(index):
    return ResearchResourceRequest(
        job_id=f"weekend-challenger-{index:02d}",
        requested_cpu_percent=Decimal("10"),
        requested_memory_bytes=1_000,
        requested_disk_bytes=2_000,
        requested_datasets=1,
        requested_experiments=1,
        maximum_runtime_seconds=1_800,
    )


def test_weekend_backtest_pressure_stays_inside_research_partition():
    queue = ResearchJobQueue()
    limits = ResearchSchedulerLimits(
        maximum_cpu_percent=TOTAL_CPU - OPERATIONAL_CPU_RESERVE,
        maximum_concurrent_jobs=4,
        maximum_storage_bytes=1_200,
        maximum_market_state_age_seconds=60,
    )
    context = ResearchSchedulerContext(
        now=NOW,
        market_is_open=False,
        market_state_observed_at=NOW - timedelta(seconds=1),
        preferred_closed_market_mode=ResearchSchedulerMode.WEEKEND_RESEARCH,
        active_jobs=0,
        reserved_cpu_percent=Decimal("0"),
        storage_used_bytes=0,
    )

    result = WeekendResearchScheduler(queue, limits).schedule(
        context,
        tuple(_scheduler_job(index) for index in range(12)),
    )

    assert len(result.enqueued) == 4
    assert len(result.deferred) == 8
    assert result.cpu_percent_after == Decimal("60")
    assert result.concurrent_jobs_after == 4
    assert result.storage_bytes_after == 1_200
    assert TOTAL_CPU - result.cpu_percent_after >= OPERATIONAL_CPU_RESERVE
    assert len(queue.list()) == 4
    assert all(item.reason in {"CPU_CAP", "CONCURRENCY_CAP", "STORAGE_CAP"} for item in result.deferred)


def test_multiple_challengers_cannot_consume_operational_reserves():
    limits = ResearchResourceLimits(
        maximum_cpu_percent=TOTAL_CPU - OPERATIONAL_CPU_RESERVE,
        maximum_concurrent_jobs=6,
        maximum_memory_bytes=TOTAL_MEMORY - OPERATIONAL_MEMORY_RESERVE,
        maximum_disk_bytes=TOTAL_DISK - OPERATIONAL_DISK_RESERVE,
        maximum_datasets=6,
        maximum_experiments=6,
        maximum_runtime_seconds_per_job=1_800,
    )
    usage = ResearchResourceUsage(0, Decimal("0"), 0, 0, 0, 0)
    accepted = []
    denied = []
    governor = ResearchResourceGovernor()

    for index in range(20):
        decision = governor.evaluate(_resource_request(index), usage, limits)
        if decision.accepted:
            accepted.append(decision)
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

    assert len(accepted) == 6
    assert len(denied) == 14
    assert usage.reserved_cpu_percent == Decimal("60")
    assert usage.memory_used_bytes == 6_000
    assert usage.disk_used_bytes == 12_000
    assert TOTAL_CPU - usage.reserved_cpu_percent >= OPERATIONAL_CPU_RESERVE
    assert TOTAL_MEMORY - usage.memory_used_bytes >= OPERATIONAL_MEMORY_RESERVE
    assert TOTAL_DISK - usage.disk_used_bytes >= OPERATIONAL_DISK_RESERVE
    assert all(decision.execution_authorized is False for decision in denied)
    assert all(decision.queue_mutation_authorized is False for decision in denied)


def test_denied_challenger_is_a_pure_decision_with_no_capacity_side_effect():
    limits = ResearchResourceLimits(
        maximum_cpu_percent=Decimal("60"),
        maximum_concurrent_jobs=2,
        maximum_memory_bytes=6_000,
        maximum_disk_bytes=12_000,
        maximum_datasets=2,
        maximum_experiments=2,
        maximum_runtime_seconds_per_job=1_800,
    )
    full_usage = ResearchResourceUsage(2, Decimal("60"), 6_000, 12_000, 2, 2)
    before = full_usage

    first = ResearchResourceGovernor().evaluate(_resource_request(98), full_usage, limits)
    second = ResearchResourceGovernor().evaluate(_resource_request(99), full_usage, limits)

    assert first.accepted is False
    assert second.accepted is False
    assert full_usage == before
    assert first.blocking_reasons == second.blocking_reasons
    assert {
        "CONCURRENCY_LIMIT_REACHED",
        "CPU_LIMIT_REACHED",
        "DATASET_LIMIT_REACHED",
        "DISK_LIMIT_REACHED",
        "EXPERIMENT_LIMIT_REACHED",
        "MEMORY_LIMIT_REACHED",
    }.issubset(first.blocking_reasons)


def test_overlong_pressure_job_is_rejected_even_when_capacity_is_available():
    limits = ResearchResourceLimits(
        maximum_cpu_percent=Decimal("60"),
        maximum_concurrent_jobs=6,
        maximum_memory_bytes=6_000,
        maximum_disk_bytes=12_000,
        maximum_datasets=6,
        maximum_experiments=6,
        maximum_runtime_seconds_per_job=1_800,
    )
    empty_usage = ResearchResourceUsage(0, Decimal("0"), 0, 0, 0, 0)
    request = replace(_resource_request(1), maximum_runtime_seconds=1_801)

    result = ResearchResourceGovernor().evaluate(request, empty_usage, limits)

    assert result.accepted is False
    assert result.blocking_reasons == ("JOB_RUNTIME_LIMIT_REACHED",)
    assert result.execution_authorized is False
    assert result.queue_mutation_authorized is False
