"""R115B tool preferences are evidence based and advisory only."""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from backend.medar.request import CognitiveDomain
from backend.medar.tool_contract import ToolResultStatus
from backend.medar.tool_performance import (
    ToolFailureClass, ToolPerformanceEvent, ToolPerformanceTracker,
)
from backend.medar.tool_preference import recommend_tools


NOW = datetime(2026, 10, 4, 16, tzinfo=timezone.utc)


def _summary(tool_id, statuses, latency):
    tracker = ToolPerformanceTracker()
    for index, status in enumerate(statuses):
        failure = ToolFailureClass.NONE if status is ToolResultStatus.SUCCESS else ToolFailureClass.EXECUTION
        tracker.record(ToolPerformanceEvent(
            f"{tool_id}-{index}", "tenant-a", "owner-a", tool_id,
            CognitiveDomain.CODING, "debug", status, failure, latency, NOW,
        ))
    return tracker.summarize(
        tenant_id="tenant-a", owner_id="owner-a", tool_id=tool_id,
        domain=CognitiveDomain.CODING, task_type="debug",
    )


def test_recommendation_ranks_observed_success_then_latency_without_authority():
    slow = _summary("slow", (ToolResultStatus.SUCCESS,) * 3, 20.0)
    fast = _summary("fast", (ToolResultStatus.SUCCESS,) * 3, 5.0)
    mixed = _summary("mixed", (ToolResultStatus.SUCCESS, ToolResultStatus.FAILED), 1.0)
    result = recommend_tools(
        (slow, mixed, fast), tenant_id="tenant-a", owner_id="owner-a",
        domain=CognitiveDomain.CODING, task_type="debug",
    )
    assert result.recommended_tool_id == "fast"
    assert tuple(item.tool_id for item in result.candidates) == ("fast", "slow", "mixed")
    assert result.observed_events == 8
    assert not result.tool_authority_granted
    assert not result.new_permission_granted


def test_insufficient_observations_return_no_preference():
    one = _summary("one", (ToolResultStatus.SUCCESS,), 1.0)
    result = recommend_tools(
        (one,), tenant_id="tenant-a", owner_id="owner-a",
        domain=CognitiveDomain.CODING, task_type="debug", minimum_attempts=2,
    )
    assert result.recommended_tool_id is None
    assert result.candidates == ()
    assert result.reason_codes == ("INSUFFICIENT_OBSERVED_EVIDENCE",)


def test_cross_scope_or_duplicate_evidence_is_rejected():
    summary = _summary("tool", (ToolResultStatus.SUCCESS,) * 2, 1.0)
    with pytest.raises(PermissionError):
        recommend_tools(
            (replace(summary, owner_id="other"),), tenant_id="tenant-a", owner_id="owner-a",
            domain=CognitiveDomain.CODING, task_type="debug",
        )
    with pytest.raises(ValueError):
        recommend_tools(
            (summary, summary), tenant_id="tenant-a", owner_id="owner-a",
            domain=CognitiveDomain.CODING, task_type="debug",
        )
