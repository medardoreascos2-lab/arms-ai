"""Explicit, session-only MEDAR preference proposals; no trait inference."""

import re
from dataclasses import dataclass
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import (
    CandidateSourceType, MemoryCandidate, has_secret_like_content,
)


class PreferenceCategory(str, Enum):
    LANGUAGE = "LANGUAGE"
    STYLE = "STYLE"
    WORKFLOW = "WORKFLOW"
    TOOLS = "TOOLS"
    NOTIFICATIONS = "NOTIFICATIONS"
    RISK = "RISK"


_PATTERN = re.compile(
    r"(?i)^(?:i prefer|my preference is)\s+"
    r"(language|style|workflow|tools|notifications|risk):\s*(.+)$"
)


@dataclass(frozen=True)
class PreferenceMemoryProposal:
    candidate_id: str
    tenant_id: str
    owner_id: str
    source_reference: str
    category: PreferenceCategory
    value: str
    sensitivity: DurableSensitivity = DurableSensitivity.PERSONAL
    session_only: bool = True
    persistence_authorized: bool = False
    trading_authority: bool = False

    def __post_init__(self) -> None:
        if self.sensitivity is not DurableSensitivity.PERSONAL or not self.session_only:
            raise ValueError("preferences remain personal and session-only")
        if self.persistence_authorized or self.trading_authority:
            raise ValueError("preference cannot grant persistence or trading authority")
        if not isinstance(self.value, str) or not self.value.strip() or len(self.value) > 240:
            raise ValueError("preference value must be bounded")
        if has_secret_like_content(self.value):
            raise PermissionError("secret-like preference is not retained")


def propose_explicit_preference(candidate: MemoryCandidate) -> PreferenceMemoryProposal:
    if not isinstance(candidate, MemoryCandidate) or (
        candidate.domain is not DurableMemoryDomain.PREFERENCES
        or candidate.sensitivity is not DurableSensitivity.PERSONAL
        or candidate.source_type is not CandidateSourceType.USER_STATEMENT
        or candidate.reason_to_remember != "EXPLICIT_USER_PREFERENCE"
    ):
        raise ValueError("explicit personal preference candidate is required")
    match = _PATTERN.fullmatch(" ".join(candidate.content.split()))
    if match is None:
        raise ValueError("preference category must be explicitly labeled")
    category = PreferenceCategory(match.group(1).upper())
    return PreferenceMemoryProposal(
        candidate.candidate_id, candidate.tenant_id, candidate.owner_id,
        candidate.source_reference, category, match.group(2).strip(),
    )
