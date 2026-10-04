"""Structured summaries of explicitly labeled, process-local session items."""

import re
from dataclasses import dataclass
from enum import Enum

from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.session_working_memory import WorkingMemorySnapshot


class SessionSummaryCategory(str, Enum):
    GOAL = "GOAL"
    DECISION = "DECISION"
    FACT = "FACT"
    OPEN_TASK = "OPEN_TASK"
    OUTCOME = "OUTCOME"


_LABELS = {
    "goal": SessionSummaryCategory.GOAL,
    "decision": SessionSummaryCategory.DECISION,
    "fact": SessionSummaryCategory.FACT,
    "open task": SessionSummaryCategory.OPEN_TASK,
    "outcome": SessionSummaryCategory.OUTCOME,
}
_PATTERN = re.compile(r"^(goal|decision|fact|open task|outcome):\s*(.+)$", re.IGNORECASE)
_FORBIDDEN = re.compile(r"(?i)\b(?:chain[- ]of[- ]thought|hidden reasoning|private reasoning|scratchpad)\b")


@dataclass(frozen=True)
class SessionSummaryPoint:
    category: SessionSummaryCategory
    text: str
    source_reference: str

    def __post_init__(self) -> None:
        if not self.text.strip() or not self.source_reference.strip():
            raise ValueError("summary point needs content and source")
        if has_secret_like_content(self.text) or _FORBIDDEN.search(self.text):
            raise PermissionError("secret-like or hidden-reasoning text cannot be summarized")


@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    tenant_id: str
    owner_id: str
    goals: tuple[SessionSummaryPoint, ...]
    decisions: tuple[SessionSummaryPoint, ...]
    facts: tuple[SessionSummaryPoint, ...]
    open_tasks: tuple[SessionSummaryPoint, ...]
    outcomes: tuple[SessionSummaryPoint, ...]
    omitted_items: int
    hidden_chain_of_thought_stored: bool = False
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if self.hidden_chain_of_thought_stored or self.persistence_performed:
            raise ValueError("session summaries cannot persist hidden reasoning or memory")


def summarize_session(snapshot: WorkingMemorySnapshot, *, max_points: int = 20, max_point_chars: int = 240) -> SessionSummary:
    if not isinstance(snapshot, WorkingMemorySnapshot):
        raise TypeError("working memory snapshot is required")
    if isinstance(max_points, bool) or not isinstance(max_points, int) or not 1 <= max_points <= 100:
        raise ValueError("max_points must be 1 to 100")
    if isinstance(max_point_chars, bool) or not isinstance(max_point_chars, int) or not 1 <= max_point_chars <= 1000:
        raise ValueError("max_point_chars must be 1 to 1000")
    grouped: dict[SessionSummaryCategory, list[SessionSummaryPoint]] = {category: [] for category in SessionSummaryCategory}
    omitted = 0
    # Only user-visible, explicitly labeled temporary items are summarized.
    # Candidate and retrieved durable memories remain separate, not inferred as session events.
    for item in snapshot.temporary:
        match = _PATTERN.fullmatch(" ".join(item.content.split()))
        if match is None:
            omitted += 1
            continue
        text = match.group(2).strip()
        if len(text) > max_point_chars or has_secret_like_content(text) or _FORBIDDEN.search(text):
            omitted += 1
            continue
        if sum(len(points) for points in grouped.values()) >= max_points:
            omitted += 1
            continue
        category = _LABELS[match.group(1).casefold()]
        point = SessionSummaryPoint(category, text, item.source_reference)
        if point not in grouped[category]:
            grouped[category].append(point)
    return SessionSummary(
        snapshot.session_id, snapshot.tenant_id, snapshot.owner_id,
        tuple(grouped[SessionSummaryCategory.GOAL]),
        tuple(grouped[SessionSummaryCategory.DECISION]),
        tuple(grouped[SessionSummaryCategory.FACT]),
        tuple(grouped[SessionSummaryCategory.OPEN_TASK]),
        tuple(grouped[SessionSummaryCategory.OUTCOME]),
        omitted,
    )
