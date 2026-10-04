"""R109B explicit session goal lifecycle and evidence tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.long_term_goal_memory import (
    GoalProgressEvidence, GoalState, SessionGoalTracker,
)


NOW = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
SCOPE = dict(tenant_id="tenant-a", owner_id="owner-a", session_id="session-a")


def _evidence(text="synthetic milestone observed"):
    return GoalProgressEvidence("conversation-1/turn-4", NOW, text)


def test_goal_lifecycle_requires_evidence_and_preserves_source():
    tracker = SessionGoalTracker(**SCOPE)
    goal = tracker.add_explicit("Goal: finish synthetic schema migration", "conversation-1/turn-1")
    assert goal.state is GoalState.ACTIVE
    assert goal.source_reference == "conversation-1/turn-1"
    assert goal.description not in repr(goal)
    paused = tracker.advance(goal.goal_id, GoalState.PAUSED, _evidence(), **SCOPE)
    assert paused.version == 2 and paused.progress_evidence == (_evidence(),)
    assert paused.progress_evidence[0].summary not in repr(paused.progress_evidence[0])
    active = tracker.advance(goal.goal_id, GoalState.ACTIVE, _evidence("resumed after review"), **SCOPE)
    completed = tracker.advance(goal.goal_id, GoalState.COMPLETED, _evidence("verified result"), **SCOPE)
    assert active.version == 3 and completed.version == 4
    assert completed.session_only and not completed.persistence_authorized and not completed.trading_authority
    with pytest.raises(PermissionError):
        tracker.advance(goal.goal_id, GoalState.ACTIVE, _evidence(), **SCOPE)


def test_goal_scope_and_unlabeled_or_secret_text_fail_closed():
    tracker = SessionGoalTracker(**SCOPE, max_goals=1)
    with pytest.raises(ValueError):
        tracker.add_explicit("finish migration", "turn-1")
    with pytest.raises(PermissionError):
        tracker.add_explicit("Goal: api_key: synthetic", "turn-1")
    goal = tracker.add_explicit("My goal is finish synthetic migration", "turn-1")
    with pytest.raises(ValueError):
        tracker.add_explicit("My goal is another task", "turn-2")
    with pytest.raises(PermissionError):
        tracker.get(goal.goal_id, tenant_id="tenant-b", owner_id="owner-a", session_id="session-a")
    with pytest.raises(PermissionError):
        tracker.advance(goal.goal_id, GoalState.COMPLETED, _evidence(), tenant_id="tenant-a", owner_id="owner-b", session_id="session-a")
    assert tracker.get(goal.goal_id, **SCOPE).state is GoalState.ACTIVE


def test_goal_transition_rejects_missing_or_secret_progress():
    tracker = SessionGoalTracker(**SCOPE)
    goal = tracker.add_explicit("Goal: finish synthetic migration", "turn-1")
    with pytest.raises(ValueError):
        tracker.advance(goal.goal_id, GoalState.COMPLETED, None, **SCOPE)
    with pytest.raises(PermissionError):
        _evidence("password: synthetic")
    assert tracker.get(goal.goal_id, **SCOPE).version == 1
