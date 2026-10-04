"""Conservative save-policy recommendation for MEDAR memory candidates.

A disposition is advisory; no result from this module grants persistence.
"""

from dataclasses import dataclass
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import CandidateImportance, CandidateSourceType, MemoryCandidate, has_secret_like_content
from backend.medar.memory_importance import ImportanceAssessment


class MemorySaveDisposition(str, Enum):
    AUTO_SAVE_ALLOWED = "AUTO_SAVE_ALLOWED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    SESSION_ONLY = "SESSION_ONLY"
    DO_NOT_SAVE = "DO_NOT_SAVE"


_AUTO_DOMAINS = frozenset({
    DurableMemoryDomain.TECHNICAL, DurableMemoryDomain.CODING,
    DurableMemoryDomain.TOOL, DurableMemoryDomain.RESEARCH,
})


@dataclass(frozen=True)
class MemorySaveDecision:
    disposition: MemorySaveDisposition
    reason_codes: tuple[str, ...]
    persistence_authorized: bool = False

    def __post_init__(self) -> None:
        if self.persistence_authorized:
            raise ValueError("save policy cannot authorize persistence")


def evaluate_memory_save(
    candidate: MemoryCandidate,
    assessment: ImportanceAssessment,
    *,
    encryption_ready: bool = False,
) -> MemorySaveDecision:
    if not isinstance(encryption_ready, bool):
        raise TypeError("encryption_ready must be boolean")
    if has_secret_like_content(candidate.content):
        return MemorySaveDecision(MemorySaveDisposition.DO_NOT_SAVE, ("SECRET_LIKE_CONTENT",))
    if candidate.domain is DurableMemoryDomain.WORKING:
        return MemorySaveDecision(MemorySaveDisposition.SESSION_ONLY, ("WORKING_MEMORY",))
    if candidate.sensitivity in (
        DurableSensitivity.PERSONAL, DurableSensitivity.SENSITIVE,
        DurableSensitivity.HIGHLY_SENSITIVE,
    ):
        if not encryption_ready:
            return MemorySaveDecision(MemorySaveDisposition.DO_NOT_SAVE, ("ENCRYPTION_UNAVAILABLE",))
        return MemorySaveDecision(MemorySaveDisposition.REVIEW_REQUIRED, ("SENSITIVE_REVIEW_REQUIRED",))
    if (
        candidate.domain in _AUTO_DOMAINS
        and candidate.source_type is CandidateSourceType.TASK_OUTCOME
        and assessment.importance in (CandidateImportance.HIGH, CandidateImportance.CRITICAL)
        and candidate.confidence >= 0.8
    ):
        return MemorySaveDecision(MemorySaveDisposition.AUTO_SAVE_ALLOWED, ("VERIFIED_NON_SENSITIVE_OUTCOME",))
    return MemorySaveDecision(MemorySaveDisposition.REVIEW_REQUIRED, ("DEFAULT_REVIEW",))
