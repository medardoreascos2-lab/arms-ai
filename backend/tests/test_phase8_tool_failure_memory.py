"""R115C known tool failures are retrieved before retries without authority."""

from datetime import datetime, timezone

import pytest

from backend.medar.request import CognitiveDomain
from backend.medar.tool_contract import ToolResultStatus
from backend.medar.tool_failure_memory import ToolFailureMemory, known_failure_from_event
from backend.medar.tool_performance import ToolFailureClass, ToolPerformanceEvent


NOW = datetime(2026, 10, 4, 17, tzinfo=timezone.utc)


def _event(status=ToolResultStatus.FAILED, failure=ToolFailureClass.UNAVAILABLE):
    return ToolPerformanceEvent(
        "event-1", "tenant-a", "owner-a", "browser", CognitiveDomain.WEB_RESEARCH,
        "source lookup", status, failure, 25.0, NOW,
    )


def test_known_issue_is_retrieved_for_same_scoped_tool_path_before_retry():
    failure = known_failure_from_event(
        _event(), failure_id="failure-1", issue_code="SERVICE_UNAVAILABLE",
        issue_summary="synthetic endpoint was unavailable",
        recovery_guidance="check availability before a later retry",
    )
    memory = ToolFailureMemory()
    memory.remember(failure)
    found = memory.before_retry(
        tenant_id="tenant-a", owner_id="owner-a", tool_id="browser",
        domain=CognitiveDomain.WEB_RESEARCH, task_type="source lookup",
    )
    assert found == (failure,)
    assert found[0].evidence_event_id == "event-1"
    assert not found[0].retry_authority and not found[0].tool_authority


def test_cross_owner_or_different_tool_path_cannot_retrieve_failure():
    memory = ToolFailureMemory()
    memory.remember(known_failure_from_event(
        _event(), failure_id="failure-1", issue_code="UNAVAILABLE",
        issue_summary="synthetic issue", recovery_guidance="verify availability",
    ))
    assert memory.before_retry(
        tenant_id="tenant-a", owner_id="other", tool_id="browser",
        domain=CognitiveDomain.WEB_RESEARCH, task_type="source lookup",
    ) == ()
    assert memory.before_retry(
        tenant_id="tenant-a", owner_id="owner-a", tool_id="calculator",
        domain=CognitiveDomain.WEB_RESEARCH, task_type="source lookup",
    ) == ()


def test_success_secret_content_and_duplicates_are_rejected():
    with pytest.raises(ValueError):
        known_failure_from_event(
            _event(ToolResultStatus.SUCCESS, ToolFailureClass.NONE), failure_id="failure-1",
            issue_code="NONE", issue_summary="none", recovery_guidance="none",
        )
    with pytest.raises(PermissionError):
        known_failure_from_event(
            _event(), failure_id="failure-1", issue_code="UNAVAILABLE",
            issue_summary="api_key: synthetic", recovery_guidance="verify availability",
        )
    memory = ToolFailureMemory()
    failure = known_failure_from_event(
        _event(), failure_id="failure-1", issue_code="UNAVAILABLE",
        issue_summary="synthetic issue", recovery_guidance="verify availability",
    )
    memory.remember(failure)
    with pytest.raises(ValueError):
        memory.remember(failure)
