"""R112D life advisory memory requires authorization and remains advisory."""

from datetime import datetime, timezone

import pytest

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.life_advisory_memory import LifeAdvisoryMemory


NOW = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)


def _memory(**changes):
    values = dict(
        tenant_id="tenant-a", owner_id="owner-a", session_id="session-a",
        source_reference="synthetic-test:life-note-1",
        authorization_reference="synthetic-test:user-approval-1",
        goals=("finish synthetic project",), priorities=("protect test quality",),
        decision="continue the synthetic milestone", outcome="milestone remained local",
        observed_at=NOW,
    )
    values.update(changes)
    return LifeAdvisoryMemory(**values)


def test_authorized_life_advisory_tracks_only_requested_fields_without_action_authority():
    memory = _memory()
    assert memory.goals == ("finish synthetic project",)
    assert memory.priorities == ("protect test quality",)
    assert memory.domain is DurableMemoryDomain.LIFE
    assert memory.sensitivity is DurableSensitivity.PERSONAL
    assert memory.user_authorized and memory.session_only and memory.advisory_only
    assert not memory.contains_intimate_details and not memory.action_authority
    assert memory.decision not in repr(memory)


@pytest.mark.parametrize("change", [
    {"authorization_reference": ""}, {"user_authorized": False},
    {"contains_intimate_details": True}, {"session_only": False},
    {"advisory_only": False}, {"action_authority": True},
    {"domain": DurableMemoryDomain.PERSONAL},
    {"sensitivity": DurableSensitivity.PUBLIC},
    {"observed_at": datetime(2026, 10, 4)},
])
def test_life_advisory_rejects_missing_authority_intimate_content_or_weakened_bounds(change):
    with pytest.raises((PermissionError, ValueError)):
        _memory(**change)


def test_life_advisory_rejects_secret_like_or_unbounded_content():
    with pytest.raises(PermissionError):
        _memory(decision="api_key: synthetic")
    with pytest.raises(ValueError):
        _memory(goals=())
    with pytest.raises(ValueError):
        _memory(priorities=("x" * 1025,))
