"""Session-to-durable promotion proposals with no implicit write authority."""

from dataclasses import dataclass
from enum import Enum

from backend.medar.memory_candidates import MemoryCandidate, has_secret_like_content
from backend.medar.memory_importance import ImportanceEvidence, score_memory_importance
from backend.medar.memory_save_policy import MemorySaveDisposition, evaluate_memory_save
from backend.medar.session_working_memory import WorkingMemorySnapshot


class PromotionDisposition(str, Enum):
    READY_FOR_AUTHORIZED_WRITE = "READY_FOR_AUTHORIZED_WRITE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class MemoryPromotionProposal:
    session_id: str
    tenant_id: str
    owner_id: str
    source_reference: str
    candidate: MemoryCandidate
    disposition: PromotionDisposition
    reason_codes: tuple[str, ...]
    persistence_authorized: bool = False
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if self.persistence_authorized or self.persistence_performed:
            raise ValueError("promotion proposal cannot authorize or perform persistence")
        if self.candidate.tenant_id != self.tenant_id or self.candidate.owner_id != self.owner_id:
            raise PermissionError("promotion candidate scope mismatch")
        if self.candidate.source_reference != self.source_reference:
            raise ValueError("promotion source reference mismatch")


def prepare_memory_promotion(
    snapshot: WorkingMemorySnapshot,
    candidate_id: str,
    evidence: ImportanceEvidence,
) -> MemoryPromotionProposal:
    if not isinstance(snapshot, WorkingMemorySnapshot) or not isinstance(evidence, ImportanceEvidence):
        raise TypeError("session snapshot and importance evidence are required")
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("candidate_id is required")
    matches = [candidate for candidate in snapshot.candidate_durable if candidate.candidate_id == candidate_id]
    if len(matches) != 1:
        raise ValueError("candidate must appear exactly once in the session snapshot")
    candidate = matches[0]
    if candidate.tenant_id != snapshot.tenant_id or candidate.owner_id != snapshot.owner_id:
        raise PermissionError("candidate owner scope mismatch")
    assessment = score_memory_importance(candidate, evidence)
    decision = evaluate_memory_save(candidate, assessment, encryption_ready=False)
    if has_secret_like_content(candidate.content) or decision.disposition is MemorySaveDisposition.DO_NOT_SAVE:
        disposition = PromotionDisposition.BLOCKED
    elif decision.disposition is MemorySaveDisposition.AUTO_SAVE_ALLOWED:
        disposition = PromotionDisposition.READY_FOR_AUTHORIZED_WRITE
    else:
        disposition = PromotionDisposition.REVIEW_REQUIRED
    return MemoryPromotionProposal(
        snapshot.session_id, snapshot.tenant_id, snapshot.owner_id,
        candidate.source_reference, candidate, disposition,
        decision.reason_codes,
    )
