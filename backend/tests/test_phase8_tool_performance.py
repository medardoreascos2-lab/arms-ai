"""R115A tool measurements are scoped, typed, and authority-free."""

from datetime import datetime, timezone

import pytest

from backend.medar.request import CognitiveDomain
from backend.medar.tool_contract import ToolResultStatus
from backend.medar.tool_performance import (
    ToolFailureClass, ToolPerformanceEvent, ToolPerformanceTracker,
)


NOW = datetime(2026, 10, 4, 15, tzinfo=timezone.utc)


def _event(event_id, status, failure, latency, *, owner="owner-a", task="calculation"):
    return ToolPerformanceEvent(
        event_id, "tenant-a", owner, "calculator", CognitiveDomain.FINANCIAL,
        task, status, failure, latency, NOW,
    )


def test_tracker_measures_success_failure_latency_domain_and_task_type():
    tracker = ToolPerformanceTracker()
    tracker.record(_event("e1", ToolResultStatus.SUCCESS, ToolFailureClass.NONE, 10.0))
    tracker.record(_event("e2", ToolResultStatus.FAILED, ToolFailureClass.VALIDATION, 20.0))
    tracker.record(_event("e3", ToolResultStatus.BLOCKED, ToolFailureClass.BLOCKED, 0.0))
    tracker.record(_event("e4", ToolResultStatus.SUCCESS, ToolFailureClass.NONE, 999.0, owner="other"))
    summary = tracker.summarize(
        tenant_id="tenant-a", owner_id="owner-a", tool_id="calculator",
        domain=CognitiveDomain.FINANCIAL, task_type="calculation",
    )
    assert summary.attempts == 3 and summary.successes == 1
    assert summary.success_rate == pytest.approx(1 / 3)
    assert summary.average_latency_ms == 10.0
    assert dict(summary.failure_counts) == {
        ToolFailureClass.BLOCKED: 1, ToolFailureClass.VALIDATION: 1,
    }
    assert not summary.recommendation_authority


def test_empty_scoped_summary_is_explicit_zero_evidence():
    summary = ToolPerformanceTracker().summarize(
        tenant_id="tenant-a", owner_id="owner-a", tool_id="missing",
        domain=CognitiveDomain.CODING, task_type="debug",
    )
    assert summary.attempts == 0
    assert summary.success_rate == 0.0
    assert summary.failure_counts == ()


def test_invalid_status_failure_pair_latency_and_duplicate_are_rejected():
    with pytest.raises(ValueError):
        _event("e1", ToolResultStatus.SUCCESS, ToolFailureClass.EXECUTION, 1.0)
    with pytest.raises(ValueError):
        _event("e1", ToolResultStatus.FAILED, ToolFailureClass.NONE, 1.0)
    with pytest.raises(ValueError):
        _event("e1", ToolResultStatus.SUCCESS, ToolFailureClass.NONE, float("nan"))
    tracker = ToolPerformanceTracker()
    event = _event("e1", ToolResultStatus.SUCCESS, ToolFailureClass.NONE, 1.0)
    tracker.record(event)
    with pytest.raises(ValueError):
        tracker.record(event)
    with pytest.raises(ValueError):
        tracker.summarize(
            tenant_id="tenant-a", owner_id="owner-a", tool_id=" ",
            domain=CognitiveDomain.CODING, task_type="debug",
        )
