"""Explicit, session-only goal tracking with traceable progress evidence."""

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum

from backend.medar.memory_candidates import has_secret_like_content


class GoalState(str, Enum):
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    SUPERSEDED = "SUPERSEDED"


_ALLOWED = {
    GoalState.ACTIVE: frozenset({GoalState.PAUSED, GoalState.COMPLETED, GoalState.SUPERSEDED}),
    GoalState.PAUSED: frozenset({GoalState.ACTIVE, GoalState.COMPLETED, GoalState.SUPERSEDED}),
    GoalState.COMPLETED: frozenset(),
    GoalState.SUPERSEDED: frozenset(),
}
_GOAL_PATTERN = re.compile(r"(?i)^(?:goal:|my goal is)\s*(.+)$")


@dataclass(frozen=True)
class GoalProgressEvidence:
    source_reference: str
    observed_at: datetime
    summary: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_reference, str) or not self.source_reference.strip():
            raise ValueError("progress source is required")
        if not isinstance(self.summary, str) or not self.summary.strip() or len(self.summary) > 240:
            raise ValueError("progress summary must be bounded")
        if has_secret_like_content(self.summary):
            raise PermissionError("secret-like progress is not retained")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("progress time must be timezone-aware")


@dataclass(frozen=True)
class SessionGoal:
    goal_id: str
    tenant_id: str
    owner_id: str
    session_id: str
    description: str
    source_reference: str
    state: GoalState
    version: int
    progress_evidence: tuple[GoalProgressEvidence, ...]
    session_only: bool = True
    persistence_authorized: bool = False
    trading_authority: bool = False

    def __post_init__(self) -> None:
        if not self.session_only or self.persistence_authorized or self.trading_authority:
            raise ValueError("goal tracking cannot persist or authorize trading")
        if not isinstance(self.description, str) or not self.description.strip() or len(self.description) > 240:
            raise ValueError("goal description must be bounded")
        if has_secret_like_content(self.description):
            raise PermissionError("secret-like goal is not retained")
        if not isinstance(self.state, GoalState) or type(self.version) is not int or self.version < 1:
            raise ValueError("goal state and version are required")


class SessionGoalTracker:
    def __init__(self, tenant_id: str, owner_id: str, session_id: str, *, max_goals: int = 100):
        for name, value in (("tenant_id", tenant_id), ("owner_id", owner_id), ("session_id", session_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if type(max_goals) is not int or not 1 <= max_goals <= 1000:
            raise ValueError("max_goals must be 1 to 1000")
        self.tenant_id = tenant_id
        self.owner_id = owner_id
        self.session_id = session_id
        self.max_goals = max_goals
        self._goals: dict[str, SessionGoal] = {}

    def add_explicit(self, statement: str, source_reference: str) -> SessionGoal:
        if not isinstance(statement, str) or not isinstance(source_reference, str) or not source_reference.strip():
            raise ValueError("goal statement and source are required")
        match = _GOAL_PATTERN.fullmatch(" ".join(statement.split()))
        if match is None:
            raise ValueError("goal must be explicitly labeled")
        description = match.group(1).strip()
        if len(self._goals) >= self.max_goals:
            raise ValueError("session goal capacity exceeded")
        digest = hashlib.sha256(chr(31).join((self.tenant_id, self.owner_id, self.session_id, source_reference, description)).encode()).hexdigest()
        if digest in self._goals:
            raise ValueError("goal source already tracked")
        goal = SessionGoal(digest, self.tenant_id, self.owner_id, self.session_id,
                           description, source_reference, GoalState.ACTIVE, 1, ())
        self._goals[digest] = goal
        return goal

    def get(self, goal_id: str, *, tenant_id: str, owner_id: str, session_id: str) -> SessionGoal | None:
        self._require_scope(tenant_id, owner_id, session_id)
        return self._goals.get(goal_id)

    def advance(self, goal_id: str, new_state: GoalState, evidence: GoalProgressEvidence, *, tenant_id: str, owner_id: str, session_id: str) -> SessionGoal:
        self._require_scope(tenant_id, owner_id, session_id)
        goal = self._goals.get(goal_id)
        if goal is None:
            raise ValueError("goal not found")
        if not isinstance(new_state, GoalState) or new_state not in _ALLOWED[goal.state]:
            raise PermissionError("goal transition is not allowed")
        if not isinstance(evidence, GoalProgressEvidence):
            raise ValueError("progress evidence is required")
        if len(goal.progress_evidence) >= 100:
            raise ValueError("goal progress evidence capacity exceeded")
        updated = replace(goal, state=new_state, version=goal.version + 1,
                          progress_evidence=goal.progress_evidence + (evidence,))
        self._goals[goal_id] = updated
        return updated

    def _require_scope(self, tenant_id: str, owner_id: str, session_id: str) -> None:
        if (tenant_id, owner_id, session_id) != (self.tenant_id, self.owner_id, self.session_id):
            raise PermissionError("goal session scope mismatch")
