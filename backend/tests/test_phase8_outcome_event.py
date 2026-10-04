"""R114A outcome event contract tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.outcome_event import OutcomeEvent


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _event(**changes):
    values = dict(
        event_id="outcome-1", tenant_id="tenant-a", owner_id="owner-a",
        session_id="session-a", source_reference="synthetic-test:task-1",
        task="run synthetic validation", decision="use bounded validation",
        prediction="all synthetic checks pass", expected_result="green result",
        observed_result="green result", success_metric="all assertions pass",
        error=None, timestamp=NOW,
    )
    values.update(changes)
    return OutcomeEvent(**values)


def test_outcome_event_captures_required_fields_without_authority():
    event = _event()
    assert event.task == "run synthetic validation"
    assert event.decision == "use bounded validation"
    assert event.prediction == "all synthetic checks pass"
    assert event.expected_result == event.observed_result
    assert event.success_metric == "all assertions pass"
    assert event.error is None and event.timestamp is NOW
    assert not event.execution_authority and not event.model_update_authority
    assert event.observed_result not in repr(event)


@pytest.mark.parametrize("change", [
    {"event_id": ""}, {"observed_result": ""},
    {"timestamp": datetime(2026, 10, 4)},
    {"execution_authority": True}, {"model_update_authority": True},
])
def test_outcome_event_rejects_invalid_trace_or_authority(change):
    with pytest.raises(ValueError):
        _event(**change)


def test_outcome_event_rejects_secret_like_content():
    with pytest.raises(PermissionError):
        _event(error="access_token: synthetic")
