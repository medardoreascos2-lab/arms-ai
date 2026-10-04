"""Separate, fail-closed MEDAR durable-write decision authority.

This foundation never writes a record. Encryption and runtime integration must be
validated before AUTHORIZED can be returned.
"""

from dataclasses import dataclass
from enum import Enum
from secrets import token_hex

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.controlled_memory_promotion import PromotionDisposition, prepare_memory_promotion
from backend.medar.durable_memory_record import DurableSensitivity, RetentionPolicy, content_digest
from backend.medar.memory_importance import ImportanceEvidence
from backend.medar.session_working_memory import WorkingMemorySnapshot
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


class DurableWriteStatus(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED_IDENTITY = "BLOCKED_IDENTITY"
    BLOCKED_ENCRYPTION = "BLOCKED_ENCRYPTION"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    BLOCKED_SENSITIVITY = "BLOCKED_SENSITIVITY"
    BLOCKED_RETENTION = "BLOCKED_RETENTION"


@dataclass(frozen=True)
class DurableWriteDecision:
    status: DurableWriteStatus
    reason_code: str
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if self.persistence_performed:
            raise ValueError("write decision cannot persist memory")


@dataclass(frozen=True)
class CandidateApproval:
    approval_id: str
    runtime_identity_id: str
    candidate_id: str
    content_hash: str
    source_reference: str
    session_id: str
    tenant_id: str
    owner_id: str


class DurableMemoryWriteAuthority:
    """Trusted local review registry; no durable-write operation is exposed."""

    def __init__(self, identity_authority: LocalAdminIdentityAuthority):
        if not isinstance(identity_authority, LocalAdminIdentityAuthority):
            raise TypeError("trusted runtime identity authority is required")
        self._identity_authority = identity_authority
        self._approvals: dict[str, CandidateApproval] = {}

    def _matches_scope(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        snapshot: WorkingMemorySnapshot,
    ) -> bool:
        return (
            isinstance(request, BoundMemoryRequest)
            and isinstance(snapshot, WorkingMemorySnapshot)
            and identity.owner_id == request.owner_id == snapshot.owner_id
            and identity.tenant_id == request.tenant_id == snapshot.tenant_id
            and identity.session_id == request.session_id == snapshot.session_id
            and identity.service_id == request.service_id
            and identity.purpose is request.purpose
            and RuntimeMemoryPermission.WRITE in identity.permissions
            and request.claimed_role is None
            and request.claimed_permission in (None, RuntimeMemoryPermission.WRITE)
        )

    def approve_candidate(
        self,
        identity: TrustedRuntimeIdentity,
        snapshot: WorkingMemorySnapshot,
        candidate_id: str,
    ) -> CandidateApproval:
        self._identity_authority.require_valid(identity)
        if RuntimeMemoryPermission.WRITE not in identity.permissions:
            raise PermissionError("runtime identity lacks write permission")
        if not isinstance(snapshot, WorkingMemorySnapshot) or (
            snapshot.owner_id != identity.owner_id
            or snapshot.tenant_id != identity.tenant_id
            or snapshot.session_id != identity.session_id
        ):
            raise PermissionError("candidate session scope mismatch")
        candidates = [c for c in snapshot.candidate_durable if c.candidate_id == candidate_id]
        if not isinstance(candidate_id, str) or len(candidates) != 1:
            raise ValueError("candidate must appear exactly once in session")
        candidate = candidates[0]
        approval = CandidateApproval(
            token_hex(16), identity.runtime_identity_id, candidate_id,
            content_digest(candidate.content), candidate.source_reference,
            snapshot.session_id, snapshot.tenant_id, snapshot.owner_id,
        )
        self._approvals[approval.approval_id] = approval
        return approval

    def evaluate(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        snapshot: WorkingMemorySnapshot,
        candidate_id: str,
        evidence: ImportanceEvidence,
        retention_policy: RetentionPolicy,
        approval: CandidateApproval | None = None,
    ) -> DurableWriteDecision:
        try:
            self._identity_authority.require_valid(identity)
        except PermissionError:
            return DurableWriteDecision(DurableWriteStatus.BLOCKED_IDENTITY, "IDENTITY_INVALID")
        if not self._matches_scope(identity, request, snapshot):
            return DurableWriteDecision(DurableWriteStatus.BLOCKED_IDENTITY, "IDENTITY_SCOPE_MISMATCH")
        try:
            proposal = prepare_memory_promotion(snapshot, candidate_id, evidence)
        except (TypeError, ValueError, PermissionError):
            return DurableWriteDecision(DurableWriteStatus.BLOCKED_POLICY, "CANDIDATE_INVALID")
        candidate = proposal.candidate
        if candidate.domain is not request.domain or candidate.sensitivity is not request.sensitivity:
            return DurableWriteDecision(DurableWriteStatus.BLOCKED_IDENTITY, "CANDIDATE_SCOPE_MISMATCH")
        if proposal.disposition is PromotionDisposition.BLOCKED:
            return DurableWriteDecision(DurableWriteStatus.BLOCKED_POLICY, "SAVE_POLICY_BLOCKED")
        if proposal.disposition is PromotionDisposition.REVIEW_REQUIRED:
            return DurableWriteDecision(DurableWriteStatus.REVIEW_REQUIRED, "SAVE_POLICY_REVIEW_REQUIRED")
        if approval is None or not isinstance(approval, CandidateApproval) or (
            self._approvals.get(approval.approval_id) is not approval
            or approval.runtime_identity_id != identity.runtime_identity_id
            or approval.candidate_id != candidate_id
            or approval.content_hash != content_digest(candidate.content)
            or approval.source_reference != candidate.source_reference
            or approval.session_id != snapshot.session_id
            or approval.owner_id != snapshot.owner_id
            or approval.tenant_id != snapshot.tenant_id
        ):
            return DurableWriteDecision(DurableWriteStatus.REVIEW_REQUIRED, "CANDIDATE_APPROVAL_REQUIRED")
        if candidate.sensitivity not in (DurableSensitivity.PUBLIC, DurableSensitivity.INTERNAL):
            return DurableWriteDecision(DurableWriteStatus.BLOCKED_SENSITIVITY, "SENSITIVE_WRITE_NOT_VALIDATED")
        if not isinstance(retention_policy, RetentionPolicy) or retention_policy is RetentionPolicy.SESSION:
            return DurableWriteDecision(DurableWriteStatus.BLOCKED_RETENTION, "DURABLE_RETENTION_REQUIRED")
        return DurableWriteDecision(DurableWriteStatus.BLOCKED_ENCRYPTION, "APPROVED_ENCRYPTION_NOT_VALIDATED")
