"""Synthetic local-test durable promotion after every independent gate passes."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_record import (
    DurableMemoryRecord, DurableMemoryType, MemoryLifecycle,
    ProvenanceClass, RetentionPolicy, content_digest,
)
from backend.medar.durable_write_authority import (
    CandidateApproval, DurableMemoryWriteAuthority, DurableWriteStatus,
)
from backend.medar.memory_candidates import CandidateImportance
from backend.medar.memory_importance import ImportanceEvidence, score_memory_importance
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.session_working_memory import WorkingMemorySnapshot
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import TrustedRuntimeIdentity
from backend.medar.encrypted_memory_envelope import EncryptedMemoryEnvelope


class EncryptedEnvelopeWriter(Protocol):
    def write(self, scope: MemoryScope, envelope: EncryptedMemoryEnvelope) -> None: ...


_IMPORTANCE_SCORE = {
    CandidateImportance.LOW: 0.2,
    CandidateImportance.MEDIUM: 0.5,
    CandidateImportance.HIGH: 0.8,
    CandidateImportance.CRITICAL: 1.0,
}


@dataclass(frozen=True)
class SyntheticPromotionReceipt:
    memory_id: str
    session_id: str
    source_reference: str
    owner_id: str
    tenant_id: str
    key_reference: str
    key_version: str
    local_test_only: bool = True
    production_promotion_authorized: bool = False

    def __post_init__(self) -> None:
        if not self.local_test_only or self.production_promotion_authorized:
            raise ValueError("synthetic promotion cannot claim production authority")


def promote_synthetic_memory(
    authority: DurableMemoryWriteAuthority,
    identity: TrustedRuntimeIdentity,
    request: BoundMemoryRequest,
    snapshot: WorkingMemorySnapshot,
    candidate_id: str,
    evidence: ImportanceEvidence,
    retention_policy: RetentionPolicy,
    approval: CandidateApproval,
    store: EncryptedEnvelopeWriter,
    *,
    clock=None,
) -> SyntheticPromotionReceipt:
    if not isinstance(authority, DurableMemoryWriteAuthority):
        raise TypeError("durable write authority is required")
    decision = authority.evaluate(
        identity, request, snapshot, candidate_id, evidence, retention_policy, approval,
    )
    if decision.status is not DurableWriteStatus.AUTHORIZED or not decision.local_test_only:
        raise PermissionError("synthetic durable promotion is blocked")
    candidates = [item for item in snapshot.candidate_durable if item.candidate_id == candidate_id]
    if len(candidates) != 1:
        raise ValueError("candidate disappeared before promotion")
    candidate = candidates[0]
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("promotion clock must be timezone-aware")
    assessment = score_memory_importance(candidate, evidence)
    provenance = MemoryProvenance(
        candidate.source_reference, MemoryOrigin.OBSERVED, now,
        candidate.tenant_id, candidate.owner_id, snapshot.session_id,
        candidate.confidence,
    )
    record = DurableMemoryRecord(
        candidate.candidate_id, candidate.owner_id, candidate.tenant_id,
        candidate.domain, DurableMemoryType.OUTCOME,
        candidate.content, content_digest(candidate.content),
        "synthetic_test", candidate.source_reference,
        provenance, ProvenanceClass.DIRECT_OBSERVATION,
        candidate.confidence, _IMPORTANCE_SCORE[assessment.importance],
        candidate.sensitivity, now, now, None, retention_policy,
        MemoryLifecycle.ACTIVE, 1,
    )
    envelope = authority.seal_synthetic(record)
    store.write(MemoryScope(record.tenant_id, record.owner_id), envelope)
    return SyntheticPromotionReceipt(
        record.memory_id, snapshot.session_id, candidate.source_reference,
        record.owner_id, record.tenant_id,
        envelope.payload.key_reference, envelope.payload.key_version,
    )
