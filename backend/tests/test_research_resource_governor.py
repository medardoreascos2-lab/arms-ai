from dataclasses import replace
from decimal import Decimal

import pytest

from backend.research.resource_governor import (
    ResearchResourceGovernor, ResearchResourceLimits, ResearchResourceRequest, ResearchResourceUsage,
)

LIMITS = ResearchResourceLimits(Decimal("80"), 4, 1000, 2000, 10, 20, 3600)
USAGE = ResearchResourceUsage(1, Decimal("20"), 100, 200, 1, 2)
REQUEST = ResearchResourceRequest("job-1", Decimal("10"), 100, 100, 1, 1, 600)


def test_request_within_every_budget_is_admitted_without_side_effect_authority() -> None:
    result = ResearchResourceGovernor().evaluate(REQUEST, USAGE, LIMITS)
    assert result.accepted and result.blocking_reasons == ()
    assert result.projected_cpu_percent == Decimal("30")
    assert result.projected_concurrent_jobs == 2
    assert result.execution_authorized is False
    assert result.queue_mutation_authorized is False


@pytest.mark.parametrize("usage,job_request,reason", [
    (replace(USAGE, reserved_cpu_percent=Decimal("75")), REQUEST, "CPU_LIMIT_REACHED"),
    (replace(USAGE, active_jobs=4), REQUEST, "CONCURRENCY_LIMIT_REACHED"),
    (replace(USAGE, memory_used_bytes=950), REQUEST, "MEMORY_LIMIT_REACHED"),
    (replace(USAGE, disk_used_bytes=1950), REQUEST, "DISK_LIMIT_REACHED"),
    (replace(USAGE, dataset_count=10), REQUEST, "DATASET_LIMIT_REACHED"),
    (replace(USAGE, experiment_count=20), REQUEST, "EXPERIMENT_LIMIT_REACHED"),
    (USAGE, replace(REQUEST, maximum_runtime_seconds=3601), "JOB_RUNTIME_LIMIT_REACHED"),
])
def test_each_resource_limit_fails_closed(usage, job_request, reason: str) -> None:
    result = ResearchResourceGovernor().evaluate(job_request, usage, LIMITS)
    assert result.accepted is False
    assert reason in result.blocking_reasons


def test_all_exceeded_limits_are_reported_together() -> None:
    usage = ResearchResourceUsage(4, Decimal("80"), 1000, 2000, 10, 20)
    result = ResearchResourceGovernor().evaluate(replace(REQUEST, maximum_runtime_seconds=3601), usage, LIMITS)
    assert len(result.blocking_reasons) == 7


def test_exact_limits_are_allowed() -> None:
    limits = ResearchResourceLimits(Decimal("30"), 2, 200, 300, 2, 3, 600)
    assert ResearchResourceGovernor().evaluate(REQUEST, USAGE, limits).accepted


def test_invalid_negative_or_nonfinite_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        replace(USAGE, memory_used_bytes=-1)
    with pytest.raises(ValueError):
        replace(REQUEST, requested_cpu_percent=Decimal("NaN"))


def test_limits_hash_is_deterministic() -> None:
    assert LIMITS.limits_hash == ResearchResourceLimits(Decimal("80"), 4, 1000, 2000, 10, 20, 3600).limits_hash
