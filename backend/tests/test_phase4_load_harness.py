"""R47A bounded local load harness tests."""

from decimal import Decimal
from threading import Lock
import time

import pytest

from backend.phase4.load_harness import (
    IsolatedLoadHarness,
    LoadDomain,
    LoadHarnessConfig,
    LoadOperation,
)


def test_all_required_domains_are_measured_without_retaining_payloads():
    observed = []
    operations = tuple(
        LoadOperation(
            f"operation-{index:02d}",
            domain,
            lambda domain=domain: observed.append(domain),
        )
        for index, domain in enumerate(LoadDomain)
    )
    report = IsolatedLoadHarness().run(operations)
    assert set(observed) == set(LoadDomain)
    assert tuple(item.domain for item in report.metrics) == tuple(LoadDomain)
    assert all(item.attempted == 1 for item in report.metrics)
    assert all(item.succeeded == 1 for item in report.metrics)
    assert all(item.error_rate == Decimal(0) for item in report.metrics)
    assert not hasattr(report.samples[0], "result")


def test_failures_are_counted_and_sanitized_to_exception_type():
    def fail():
        raise RuntimeError("sensitive payload must not be retained")

    report = IsolatedLoadHarness().run((
        LoadOperation("read-success", LoadDomain.READ_API, lambda: None),
        LoadOperation("read-failure", LoadDomain.READ_API, fail),
    ))
    metrics = next(item for item in report.metrics if item.domain is LoadDomain.READ_API)
    failed = next(item for item in report.samples if not item.succeeded)
    assert (metrics.attempted, metrics.succeeded, metrics.failed) == (2, 1, 1)
    assert metrics.error_rate == Decimal("0.5")
    assert failed.error_code == "RuntimeError"
    assert "sensitive" not in repr(report)


def test_worker_and_submission_bounds_hold_under_concurrency():
    lock = Lock()
    active = 0
    maximum_active = 0

    def work():
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.005)
        with lock:
            active -= 1

    config = LoadHarnessConfig(maximum_workers=3, maximum_in_flight=5)
    operations = tuple(
        LoadOperation(f"bounded-{index:03d}", LoadDomain.OUTBOX, work)
        for index in range(30)
    )
    report = IsolatedLoadHarness(config).run(operations)
    assert maximum_active <= 3
    assert report.maximum_queue_depth <= 5
    assert len(report.samples) == 30


def test_report_contains_throughput_latency_error_and_queue_lag():
    report = IsolatedLoadHarness().run((
        LoadOperation("audit-0001", LoadDomain.AUDIT_LOG, lambda: None),
        LoadOperation("audit-0002", LoadDomain.AUDIT_LOG, lambda: None),
    ))
    metrics = next(item for item in report.metrics if item.domain is LoadDomain.AUDIT_LOG)
    assert metrics.throughput_per_second > 0
    assert metrics.average_latency_ns >= 0
    assert metrics.p95_latency_ns >= metrics.average_latency_ns
    assert metrics.maximum_latency_ns >= metrics.p95_latency_ns
    assert metrics.maximum_queue_lag_ns >= 0


def test_harness_has_no_external_or_trading_authority():
    harness = IsolatedLoadHarness()
    report = harness.run((
        LoadOperation("research-0001", LoadDomain.RESEARCH_QUEUE, lambda: None),
    ))
    assert harness.external_traffic_authorized is False
    assert harness.execution_authorized is False
    assert harness.production_mutation_authorized is False
    assert harness.live_trading_authorized is False
    assert report.external_traffic_authorized is False
    assert report.execution_authorized is False
    assert report.production_mutation_authorized is False
    assert report.live_trading_authorized is False


def test_invalid_bounds_and_duplicate_operations_fail_closed():
    with pytest.raises(ValueError, match="between 1 and 32"):
        LoadHarnessConfig(maximum_workers=33, maximum_in_flight=33)
    with pytest.raises(ValueError, match="cannot be less"):
        LoadHarnessConfig(maximum_workers=2, maximum_in_flight=1)
    operation = LoadOperation("duplicate-0001", LoadDomain.EVALUATION, lambda: None)
    with pytest.raises(ValueError, match="unique"):
        IsolatedLoadHarness().run((operation, operation))
