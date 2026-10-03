"""R31I tests for bounded closed-market research scheduling."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from backend.research.research_scheduler import (
    MaintenanceWindow,
    ResearchJobKind,
    ResearchJobQueue,
    ResearchJobRequest,
    ResearchSchedulerContext,
    ResearchSchedulerLimits,
    ResearchSchedulerMode,
    WeekendResearchScheduler,
)


UTC = timezone.utc
NOW = datetime(2026, 10, 3, 12, tzinfo=UTC)


def limits(**changes):
    values = dict(
        maximum_cpu_percent=Decimal("60"),
        maximum_concurrent_jobs=3,
        maximum_storage_bytes=1000,
        maximum_market_state_age_seconds=60,
        maintenance_windows=(),
    )
    values.update(changes)
    return ResearchSchedulerLimits(**values)


def context(**changes):
    values = dict(
        now=NOW,
        market_is_open=False,
        market_state_observed_at=NOW - timedelta(seconds=10),
        preferred_closed_market_mode=ResearchSchedulerMode.WEEKEND_RESEARCH,
        active_jobs=0,
        reserved_cpu_percent=Decimal("0"),
        storage_used_bytes=0,
    )
    values.update(changes)
    return ResearchSchedulerContext(**values)


def job(name="candidate-1", **changes):
    values = dict(
        strategy_id=name,
        kind=ResearchJobKind.BACKTEST,
        evidence_ids=("dataset-1", "experiment-1"),
        eligible_modes=(
            ResearchSchedulerMode.DEEP_RESEARCH,
            ResearchSchedulerMode.WEEKEND_RESEARCH,
        ),
        estimated_cpu_percent=Decimal("20"),
        estimated_storage_bytes=200,
        priority=10,
    )
    values.update(changes)
    return ResearchJobRequest(**values)


def assert_no_authority(value):
    assert value.execution_authorized is False
    assert value.production_mutation_authorized is False


def test_closed_market_enqueues_bounded_weekend_research_jobs_only():
    queue = ResearchJobQueue()
    scheduler = WeekendResearchScheduler(queue, limits())
    requests = (job("candidate-1"), job("candidate-2", priority=5))

    result = scheduler.schedule(context(), requests)

    assert result.mode is ResearchSchedulerMode.WEEKEND_RESEARCH
    assert [item.job for item in result.enqueued] == list(requests)
    assert all(item.inserted for item in result.enqueued)
    assert result.deferred == ()
    assert result.cpu_percent_after == Decimal("40")
    assert result.concurrent_jobs_after == 2
    assert result.storage_bytes_after == 400
    assert queue.list() == tuple(sorted(requests, key=lambda item: item.job_id))
    assert result.production_strategy_modified is False
    assert result.execution_authorized is False
    assert result.live_execution_authorized is False
    assert result.operating_system_scheduler_modified is False
    assert len(result.decision_id) == 64


def test_open_market_forces_live_market_mode_and_zero_queue_side_effects():
    queue = ResearchJobQueue()
    result = WeekendResearchScheduler(queue, limits()).schedule(
        context(market_is_open=True), (job(),)
    )

    assert result.mode is ResearchSchedulerMode.LIVE_MARKET
    assert result.enqueued == ()
    assert result.blocking_reasons == ("MARKET_OPEN",)
    assert result.deferred[0].reason == "MARKET_OPEN"
    assert queue.list() == ()


def test_stale_market_state_fails_closed_without_enqueue_even_if_marked_closed():
    queue = ResearchJobQueue()
    result = WeekendResearchScheduler(queue, limits()).schedule(
        context(market_state_observed_at=NOW - timedelta(seconds=61)), (job(),)
    )

    assert result.mode is ResearchSchedulerMode.IDLE
    assert result.blocking_reasons == ("MARKET_STATE_STALE",)
    assert queue.list() == ()


def test_maintenance_window_blocks_research_at_start_and_allows_at_end():
    window = MaintenanceWindow(NOW, NOW + timedelta(hours=1))
    settings = limits(maintenance_windows=(window,))
    queue = ResearchJobQueue()
    scheduler = WeekendResearchScheduler(queue, settings)

    blocked = scheduler.schedule(context(now=NOW, market_state_observed_at=NOW), (job(),))
    allowed = scheduler.schedule(
        context(
            now=NOW + timedelta(hours=1),
            market_state_observed_at=NOW + timedelta(hours=1),
        ),
        (job(),),
    )

    assert blocked.mode is ResearchSchedulerMode.IDLE
    assert blocked.blocking_reasons == ("MAINTENANCE_WINDOW",)
    assert allowed.mode is ResearchSchedulerMode.WEEKEND_RESEARCH
    assert allowed.enqueued[0].inserted is True


def test_explicit_idle_closed_market_does_not_enqueue():
    queue = ResearchJobQueue()
    result = WeekendResearchScheduler(queue, limits()).schedule(
        context(preferred_closed_market_mode=ResearchSchedulerMode.IDLE), (job(),)
    )

    assert result.mode is ResearchSchedulerMode.IDLE
    assert result.blocking_reasons == ("SCHEDULER_IDLE",)
    assert queue.list() == ()


def test_deep_research_only_job_runs_only_in_deep_mode():
    request = job(eligible_modes=(ResearchSchedulerMode.DEEP_RESEARCH,))
    weekend_queue = ResearchJobQueue()
    weekend = WeekendResearchScheduler(weekend_queue, limits()).schedule(
        context(), (request,)
    )
    deep_queue = ResearchJobQueue()
    deep = WeekendResearchScheduler(deep_queue, limits()).schedule(
        context(preferred_closed_market_mode=ResearchSchedulerMode.DEEP_RESEARCH),
        (request,),
    )

    assert weekend.enqueued == ()
    assert weekend.deferred[0].reason == "MODE_NOT_ELIGIBLE"
    assert deep.enqueued[0].inserted is True


@pytest.mark.parametrize(
    ("limit_changes", "context_changes", "job_changes", "reason"),
    (
        ({"maximum_concurrent_jobs": 1}, {"active_jobs": 1}, {}, "CONCURRENCY_CAP"),
        (
            {"maximum_cpu_percent": Decimal("50")},
            {"reserved_cpu_percent": Decimal("40")},
            {"estimated_cpu_percent": Decimal("20")},
            "CPU_CAP",
        ),
        (
            {"maximum_storage_bytes": 1000},
            {"storage_used_bytes": 900},
            {"estimated_storage_bytes": 101},
            "STORAGE_CAP",
        ),
    ),
)
def test_each_resource_cap_defers_job_without_queue_side_effects(
    limit_changes, context_changes, job_changes, reason
):
    queue = ResearchJobQueue()
    result = WeekendResearchScheduler(queue, limits(**limit_changes)).schedule(
        context(**context_changes), (job(**job_changes),)
    )

    assert result.enqueued == ()
    assert result.deferred[0].reason == reason
    assert result.blocking_reasons == (reason,)
    assert queue.list() == ()


def test_large_high_priority_job_can_defer_while_smaller_job_uses_remaining_capacity():
    queue = ResearchJobQueue()
    large = job(
        "large",
        priority=100,
        estimated_cpu_percent=Decimal("70"),
        estimated_storage_bytes=900,
    )
    small = job("small", priority=1, estimated_cpu_percent=Decimal("10"))

    result = WeekendResearchScheduler(queue, limits()).schedule(context(), (small, large))

    assert len(result.deferred) == 1
    assert result.deferred[0].job_id == large.job_id
    assert result.deferred[0].reason == "CPU_CAP"
    assert [item.job.job_id for item in result.enqueued] == [small.job_id]
    assert queue.list() == (small,)


def test_exact_retry_is_duplicate_and_does_not_double_reserve_resources():
    queue = ResearchJobQueue()
    scheduler = WeekendResearchScheduler(queue, limits())
    request = job()
    first = scheduler.schedule(context(), (request,))
    second = scheduler.schedule(context(), (request,))

    assert first.enqueued[0].inserted is True
    assert second.enqueued[0].duplicate is True
    assert second.cpu_percent_after == Decimal("0")
    assert second.concurrent_jobs_after == 0
    assert second.storage_bytes_after == 0
    assert queue.list() == (request,)


def test_priority_then_job_identity_controls_deterministic_schedule_order():
    queue = ResearchJobQueue()
    low = job("low", priority=1)
    high_b = job("high-b", priority=10)
    high_a = job("high-a", priority=10)
    expected = sorted((high_a, high_b), key=lambda item: item.job_id) + [low]

    result = WeekendResearchScheduler(queue, limits()).schedule(
        context(), (low, high_b, high_a)
    )

    assert [item.job for item in result.enqueued] == expected


def test_job_identity_is_canonical_and_queue_is_idempotent():
    first = job(
        evidence_ids=("experiment-1", "dataset-1"),
        eligible_modes=(
            ResearchSchedulerMode.WEEKEND_RESEARCH,
            ResearchSchedulerMode.DEEP_RESEARCH,
        ),
    )
    second = job(
        evidence_ids=("dataset-1", "experiment-1"),
        eligible_modes=(
            ResearchSchedulerMode.DEEP_RESEARCH,
            ResearchSchedulerMode.WEEKEND_RESEARCH,
        ),
    )
    queue = ResearchJobQueue()

    assert first == second
    assert first.job_id == second.job_id
    assert queue.enqueue(first).inserted is True
    assert queue.enqueue(second).duplicate is True
    assert_no_authority(first)
    assert_no_authority(queue)


def test_duplicate_requests_in_one_schedule_call_are_rejected_before_enqueue():
    queue = ResearchJobQueue()
    request = job()
    with pytest.raises(ValueError, match="unique job identities"):
        WeekendResearchScheduler(queue, limits()).schedule(context(), (request, request))
    assert queue.list() == ()


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"maximum_cpu_percent": Decimal("0")}, "between"),
        ({"maximum_cpu_percent": Decimal("101")}, "between"),
        ({"maximum_concurrent_jobs": 0}, ">= 1"),
        ({"maximum_storage_bytes": 0}, ">= 1"),
        ({"maximum_market_state_age_seconds": 0}, ">= 1"),
    ),
)
def test_invalid_resource_limits_are_rejected(changes, message):
    with pytest.raises(ValueError, match=message):
        limits(**changes)


def test_unsorted_or_overlapping_maintenance_windows_are_rejected():
    first = MaintenanceWindow(NOW, NOW + timedelta(hours=2))
    second = MaintenanceWindow(NOW + timedelta(hours=1), NOW + timedelta(hours=3))
    with pytest.raises(ValueError, match="overlap"):
        limits(maintenance_windows=(first, second))
    with pytest.raises(ValueError, match="sorted"):
        limits(maintenance_windows=(
            MaintenanceWindow(NOW + timedelta(days=2), NOW + timedelta(days=3)),
            MaintenanceWindow(NOW, NOW + timedelta(days=1)),
        ))


def test_invalid_or_future_scheduler_context_is_rejected():
    with pytest.raises(ValueError, match="future"):
        context(market_state_observed_at=NOW + timedelta(seconds=1))
    with pytest.raises(ValueError, match="preferred closed-market mode"):
        context(preferred_closed_market_mode=ResearchSchedulerMode.LIVE_MARKET)


@pytest.mark.parametrize(
    ("changes", "message"),
    (
        ({"eligible_modes": (ResearchSchedulerMode.IDLE,)}, "research modes"),
        ({"estimated_cpu_percent": Decimal("0")}, "between"),
        ({"estimated_storage_bytes": 0}, ">= 1"),
        ({"priority": -1}, ">= 0"),
        ({"evidence_ids": ()}, "nonempty tuple"),
    ),
)
def test_invalid_research_job_requests_are_rejected(changes, message):
    with pytest.raises(ValueError, match=message):
        job(**changes)


def test_scheduler_has_no_os_scheduler_process_or_trading_integration():
    import backend.research.research_scheduler as module

    source = Path(module.__file__).read_text(encoding="utf-8")
    assert "subprocess" not in source
    assert "Task Scheduler" not in source
    assert "EnterLong" not in source
    assert "EnterShort" not in source
    assert "broker" not in source.lower()
    assert WeekendResearchScheduler.operating_system_scheduler_modified is False
    assert WeekendResearchScheduler.production_strategy_modified is False
