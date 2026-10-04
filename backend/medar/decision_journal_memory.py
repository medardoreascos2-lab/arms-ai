"""Encrypted local-development persistence for sensitive decision journals."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from secrets import token_hex
from typing import Protocol

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.decision_journal import DecisionJournalEntry
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.encrypted_memory_envelope import EncryptedMemoryEnvelope, seal_memory_content
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_candidates import (
    CandidateImportance, CandidateSourceType, MemoryCandidate, has_secret_like_content,
)
from backend.medar.memory_encryption_readiness import EncryptionReadiness, assess_encryption_readiness
from backend.medar.memory_importance import ImportanceEvidence, score_memory_importance
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.memory_save_policy import MemorySaveDisposition, evaluate_memory_save
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


@dataclass(frozen=True)
class DecisionJournalMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    entry: DecisionJournalEntry = field(repr=False)
    lesson: str = field(repr=False)
    recorded_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.DECISION_JOURNAL
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    local_development_only: bool = True
    persistence_authorized: bool = False
    execution_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "source_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
        if not isinstance(self.entry, DecisionJournalEntry):
            raise TypeError("validated decision journal entry is required")
        content = (
            self.entry.decision, *self.entry.options, self.entry.recommendation,
            self.entry.chosen_option, self.entry.expected_outcome,
            self.entry.observed_outcome, self.lesson,
        )
        for value in content:
            if value is None:
                continue
            if not isinstance(value, str) or not value.strip() or len(value) > 1024:
                raise ValueError("journal content must be bounded explicit text")
            if has_secret_like_content(value):
                raise PermissionError("secret-like journal content is not retained")
        if not isinstance(self.recorded_at, datetime) or self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("journal record time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.DECISION_JOURNAL or self.sensitivity is not DurableSensitivity.SENSITIVE:
            raise ValueError("journal domain and sensitivity cannot be weakened")
        if not self.local_development_only or self.persistence_authorized or self.execution_authority:
            raise ValueError("journal cannot claim production, persistence, or execution authority")

    def content(self) -> str:
        return json.dumps({
            "actual_outcome": self.entry.observed_outcome,
            "chosen_option": self.entry.chosen_option,
            "decision": self.entry.decision,
            "expected_outcome": self.entry.expected_outcome,
            "lesson": self.lesson,
            "options": list(self.entry.options),
            "recommendation": self.entry.recommendation,
        }, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class DecisionJournalApproval:
    approval_id: str
    runtime_identity_id: str
    entry_id: str
    content_hash: str
    source_reference: str
    session_id: str
    tenant_id: str
    owner_id: str
    retention_policy: RetentionPolicy


@dataclass(frozen=True)
class DecisionJournalReceipt:
    memory_id: str
    owner_id: str
    tenant_id: str
    key_reference: str
    key_version: str
    algorithm_identifier: str
    local_development_only: bool = True
    production_deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if not self.local_development_only or self.production_deployment_authorized:
            raise ValueError("decision journal receipt cannot claim production authority")


class EncryptedJournalWriter(Protocol):
    def write(self, scope: MemoryScope, envelope: EncryptedMemoryEnvelope) -> None: ...


class DecisionJournalWriteAuthority:
    """Requires every independent gate before one encrypted local write."""

    def __init__(
        self,
        identity_authority: LocalAdminIdentityAuthority,
        provider: AESGCMEphemeralMemoryEncryption,
        *,
        local_development_enabled: bool = False,
    ) -> None:
        if not isinstance(identity_authority, LocalAdminIdentityAuthority):
            raise TypeError("trusted identity authority is required")
        if type(provider) is not AESGCMEphemeralMemoryEncryption:
            raise TypeError("exact AES-GCM development provider is required")
        readiness = assess_encryption_readiness(provider)
        if not local_development_enabled or (
            readiness.status is not EncryptionReadiness.LOCAL_DEVELOPMENT_READY
            or not readiness.sensitive_local_development_writes_allowed
        ):
            raise PermissionError("sensitive local-development encryption is not ready")
        self._identity_authority = identity_authority
        self._provider = provider
        self._approvals: dict[str, DecisionJournalApproval] = {}

    def _validate_scope(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        record: DecisionJournalMemory,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._identity_authority.require_valid(identity)
        if not isinstance(request, BoundMemoryRequest) or not isinstance(record, DecisionJournalMemory):
            raise TypeError("bound request and validated journal are required")
        if identity.owner_id != request.owner_id or request.owner_id != record.owner_id:
            raise PermissionError("journal owner scope mismatch")
        if identity.tenant_id != request.tenant_id or request.tenant_id != record.tenant_id:
            raise PermissionError("journal tenant scope mismatch")
        if identity.session_id != request.session_id or request.session_id != record.session_id:
            raise PermissionError("journal session scope mismatch")
        if identity.service_id != request.service_id or identity.purpose is not request.purpose:
            raise PermissionError("journal service or purpose scope mismatch")
        if identity.purpose is not MemoryPurpose.BUSINESS_ANALYSIS:
            raise PermissionError("journal persistence requires business-analysis purpose")
        if RuntimeMemoryPermission.WRITE not in identity.permissions:
            raise PermissionError("journal write permission missing")
        if request.claimed_role is not None or request.claimed_permission not in (None, RuntimeMemoryPermission.WRITE):
            raise PermissionError("caller claims cannot grant journal authority")
        if request.domain is not record.domain or request.sensitivity is not record.sensitivity:
            raise PermissionError("journal classification scope mismatch")
        if retention_policy not in (RetentionPolicy.LONG_TERM, RetentionPolicy.MANUAL_REVIEW):
            raise PermissionError("journal durable retention policy is not approved")
        if not record.source_reference.startswith("synthetic-test:"):
            raise PermissionError("local journal persistence accepts synthetic sources only")

    @staticmethod
    def _save_policy(record: DecisionJournalMemory) -> None:
        candidate = MemoryCandidate(
            candidate_id=record.entry.entry_id,
            tenant_id=record.tenant_id,
            owner_id=record.owner_id,
            source_reference=record.source_reference,
            source_type=CandidateSourceType.TASK_OUTCOME,
            content=record.content(),
            domain=record.domain,
            importance=CandidateImportance.MEDIUM,
            confidence=1.0,
            sensitivity=record.sensitivity,
            reason_to_remember="LABELED_DECISION",
        )
        assessment = score_memory_importance(
            candidate,
            ImportanceEvidence(decision=True, observed_outcome=record.entry.observed_outcome is not None),
        )
        decision = evaluate_memory_save(candidate, assessment, encryption_ready=True)
        if decision.disposition is not MemorySaveDisposition.REVIEW_REQUIRED:
            raise PermissionError("journal save policy did not require explicit review")

    def approve(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        record: DecisionJournalMemory,
        retention_policy: RetentionPolicy,
    ) -> DecisionJournalApproval:
        self._validate_scope(identity, request, record, retention_policy)
        self._save_policy(record)
        approval = DecisionJournalApproval(
            token_hex(16), identity.runtime_identity_id, record.entry.entry_id,
            content_digest(record.content()), record.source_reference,
            record.session_id, record.tenant_id, record.owner_id, retention_policy,
        )
        self._approvals[approval.approval_id] = approval
        return approval

    def persist(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        record: DecisionJournalMemory,
        retention_policy: RetentionPolicy,
        approval: DecisionJournalApproval,
        store: EncryptedJournalWriter,
    ) -> DecisionJournalReceipt:
        self._validate_scope(identity, request, record, retention_policy)
        self._save_policy(record)
        if not isinstance(approval, DecisionJournalApproval) or (
            self._approvals.get(approval.approval_id) is not approval
            or approval.runtime_identity_id != identity.runtime_identity_id
            or approval.entry_id != record.entry.entry_id
            or approval.content_hash != content_digest(record.content())
            or approval.source_reference != record.source_reference
            or approval.session_id != record.session_id
            or approval.tenant_id != record.tenant_id
            or approval.owner_id != record.owner_id
            or approval.retention_policy is not retention_policy
        ):
            raise PermissionError("journal approval is missing, stale, or scope mismatched")
        content = record.content()
        provenance = MemoryProvenance(
            record.source_reference, MemoryOrigin.OBSERVED, record.recorded_at,
            record.tenant_id, record.owner_id, record.session_id, 1.0,
        )
        durable = DurableMemoryRecord(
            record.entry.entry_id, record.owner_id, record.tenant_id,
            record.domain, DurableMemoryType.DECISION, content, content_digest(content),
            "synthetic_test", record.source_reference, provenance,
            ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.8, record.sensitivity,
            record.recorded_at, record.recorded_at, None, retention_policy,
            MemoryLifecycle.ACTIVE, 1,
        )
        envelope = seal_memory_content(durable, self._provider)
        del self._approvals[approval.approval_id]
        store.write(MemoryScope(record.tenant_id, record.owner_id), envelope)
        return DecisionJournalReceipt(
            durable.memory_id, durable.owner_id, durable.tenant_id,
            envelope.payload.key_reference, envelope.payload.key_version,
            envelope.payload.algorithm_identifier,
        )


def persist_decision_journal(
    authority: DecisionJournalWriteAuthority,
    identity: TrustedRuntimeIdentity,
    request: BoundMemoryRequest,
    record: DecisionJournalMemory,
    retention_policy: RetentionPolicy,
    approval: DecisionJournalApproval,
    writer: EncryptedJournalWriter,
) -> DecisionJournalReceipt:
    if not isinstance(authority, DecisionJournalWriteAuthority):
        raise TypeError("decision journal write authority is required")
    return authority.persist(identity, request, record, retention_policy, approval, writer)
