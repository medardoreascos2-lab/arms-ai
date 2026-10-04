"""R116C local synthetic benchmark records evidence without capability claims."""

from datetime import datetime, timezone

import pytest

from backend.medar.deterministic_model import DeterministicModelProvider, FakeResponseMode
from backend.medar.local_model_benchmark import (
    BenchmarkCategory, default_synthetic_benchmark, run_local_synthetic_benchmark,
)
from backend.medar.model_performance import ModelFailureClass


NOW = datetime(2026, 10, 4, 20, tzinfo=timezone.utc)


class StepTimer:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        self.value += 0.001
        return self.value


def test_benchmark_covers_required_categories_and_records_local_synthetic_evidence():
    result = run_local_synthetic_benchmark(
        DeterministicModelProvider(), tenant_id="tenant-a", owner_id="owner-a",
        observed_at=NOW, timer=StepTimer(),
    )
    assert {case.category for case in default_synthetic_benchmark()} == set(BenchmarkCategory)
    assert len(result.events) == 5
    assert all(event.successful and event.structured_valid for event in result.events)
    assert all(event.latency_ms == pytest.approx(1.0) for event in result.events)
    assert all(event.source_reference.startswith("synthetic-test:benchmark:") for event in result.events)
    assert result.average_quality_score == 1.0
    assert result.synthetic_only
    assert not result.external_calls_performed
    assert not result.human_intelligence_claimed
    assert not result.production_performance_claimed


def test_malformed_synthetic_provider_records_failures_without_external_calls():
    result = run_local_synthetic_benchmark(
        DeterministicModelProvider(mode=FakeResponseMode.MALFORMED),
        tenant_id="tenant-a", owner_id="owner-a", observed_at=NOW,
        timer=StepTimer(),
    )
    assert all(not event.successful for event in result.events)
    assert all(event.failure_class in (
        ModelFailureClass.PROVIDER_ERROR, ModelFailureClass.STRUCTURED_INVALID,
    ) for event in result.events)
    assert result.average_quality_score == 0.0
    assert not result.external_calls_performed


def test_failure_and_timeout_are_recorded_as_evidence_not_raised():
    failed = run_local_synthetic_benchmark(
        DeterministicModelProvider(mode=FakeResponseMode.FAILURE),
        tenant_id="tenant-a", owner_id="owner-a", observed_at=NOW,
        timer=StepTimer(),
    )
    timed_out = run_local_synthetic_benchmark(
        DeterministicModelProvider(mode=FakeResponseMode.TIMEOUT),
        tenant_id="tenant-a", owner_id="owner-a", observed_at=NOW,
        timer=StepTimer(),
    )
    assert all(event.failure_class is ModelFailureClass.PROVIDER_ERROR for event in failed.events)
    assert all(event.failure_class is ModelFailureClass.TIMEOUT for event in timed_out.events)
