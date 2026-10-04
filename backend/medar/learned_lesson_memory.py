"""Encrypted local storage for validated lessons, separate from raw outcomes."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from secrets import token_hex
from typing import Protocol

from backend.medar.bound_memory_access import BoundMemoryRequest
from backend.medar.durable_memory_encryption import AESGCMEphemeralMemoryEncryption
from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, DurableMemoryType,
    DurableSensitivity, MemoryLifecycle, ProvenanceClass, RetentionPolicy,
    content_digest,
)
from backend.medar.encrypted_memory_envelope import EncryptedMemoryEnvelope, seal_memory_content
from backend.medar.lesson_extraction import ExtractedLesson
from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.memory_encryption_readiness import EncryptionReadiness, assess_encryption_readiness
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


@dataclass(frozen=True)
class LearnedLessonMemory:
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    lesson: ExtractedLesson = field(repr=False)
    recorded_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.SEMANTIC
    sensitivity: DurableSensitivity = DurableSensitivity.SENSITIVE
    local_development_only: bool = True
    execution_authority: bool = False
    model_update_authority: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "owner_id", "session_id", "source_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 240:
                raise ValueError(f"{name} must be a bounded explicit reference")
            if has_secret_like_content(value):
                raise PermissionError("secret-like lesson metadata is not retained")
        if not isinstance(self.lesson, ExtractedLesson):
            raise TypeError("validated extracted lesson is required")
        if (
            self.tenant_id != self.lesson.tenant_id
            or self.owner_id != self.lesson.owner_id
            or self.session_id != self.lesson.session_id
            or self.source_reference != self.lesson.source_reference
        ):
            raise PermissionError("lesson memory scope must match its outcome event")
        if self.lesson.lesson_id == self.lesson.outcome_event_id:
            raise ValueError("lesson and raw outcome must use separate identities")
        if not isinstance(self.recorded_at, datetime) or self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("lesson memory time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.SEMANTIC or self.sensitivity is not DurableSensitivity.SENSITIVE:
            raise ValueError("lesson memory classification cannot be weakened")
        if not self.local_development_only or self.execution_authority or self.model_update_authority:
            raise ValueError("lesson memory cannot claim production, execution, or model update authority")

    def content(self) -> str:
        return json.dumps({
            "classification": self.lesson.classification.value,
            "conditions": self.lesson.conditions,
            "evidence_references": list(self.lesson.evidence_references),
            "future_recommendation": self.lesson.future_recommendation,
            "outcome_event_id": self.lesson.outcome_event_id,
            "what_failed": self.lesson.what_failed,
            "what_worked": self.lesson.what_worked,
        }, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class LearnedLessonApproval:
    approval_id: str
    runtime_identity_id: str
    lesson_id: str
    content_hash: str
    source_reference: str
    session_id: str
    tenant_id: str
    owner_id: str
    retention_policy: RetentionPolicy


@dataclass(frozen=True)
class LearnedLessonReceipt:
    memory_id: str
    outcome_event_id: str
    owner_id: str
    tenant_id: str
    key_reference: str
    key_version: str
    local_development_only: bool = True
    execution_authority: bool = False
    model_update_authority: bool = False

    def __post_init__(self) -> None:
        if not self.local_development_only or self.execution_authority or self.model_update_authority:
            raise ValueError("lesson receipt cannot claim production, execution, or model update authority")


class EncryptedLessonWriter(Protocol):
    def write(self, scope: MemoryScope, envelope: EncryptedMemoryEnvelope) -> None: ...


class LearnedLessonWriteAuthority:
    """Allows one separately scoped encrypted write after explicit review."""

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
        self._approvals: dict[str, LearnedLessonApproval] = {}

    def _validate_scope(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        memory: LearnedLessonMemory,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._identity_authority.require_valid(identity)
        if not isinstance(request, BoundMemoryRequest) or not isinstance(memory, LearnedLessonMemory):
            raise TypeError("bound request and validated lesson memory are required")
        if (identity.owner_id, request.owner_id, memory.owner_id) != (memory.owner_id,) * 3:
            raise PermissionError("lesson owner scope mismatch")
        if (identity.tenant_id, request.tenant_id, memory.tenant_id) != (memory.tenant_id,) * 3:
            raise PermissionError("lesson tenant scope mismatch")
        if (identity.session_id, request.session_id, memory.session_id) != (memory.session_id,) * 3:
            raise PermissionError("lesson session scope mismatch")
        if identity.service_id != request.service_id or identity.purpose is not request.purpose:
            raise PermissionError("lesson service or purpose scope mismatch")
        if RuntimeMemoryPermission.WRITE not in identity.permissions:
            raise PermissionError("lesson write permission missing")
        if request.claimed_role is not None or request.claimed_permission not in (None, RuntimeMemoryPermission.WRITE):
            raise PermissionError("caller claims cannot grant lesson authority")
        if request.domain is not memory.domain or request.sensitivity is not memory.sensitivity:
            raise PermissionError("lesson classification scope mismatch")
        if retention_policy not in (RetentionPolicy.LONG_TERM, RetentionPolicy.MANUAL_REVIEW):
            raise PermissionError("lesson durable retention policy is not approved")
        if not memory.source_reference.startswith("synthetic-test:"):
            raise PermissionError("local lesson persistence accepts synthetic sources only")

    def approve(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        memory: LearnedLessonMemory,
        retention_policy: RetentionPolicy,
    ) -> LearnedLessonApproval:
        self._validate_scope(identity, request, memory, retention_policy)
        approval = LearnedLessonApproval(
            token_hex(16), identity.runtime_identity_id, memory.lesson.lesson_id,
            content_digest(memory.content()), memory.source_reference,
            memory.session_id, memory.tenant_id, memory.owner_id, retention_policy,
        )
        self._approvals[approval.approval_id] = approval
        return approval

    def persist(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        memory: LearnedLessonMemory,
        retention_policy: RetentionPolicy,
        approval: LearnedLessonApproval,
        store: EncryptedLessonWriter,
    ) -> LearnedLessonReceipt:
        self._validate_scope(identity, request, memory, retention_policy)
        content = memory.content()
        if not isinstance(approval, LearnedLessonApproval) or (
            self._approvals.get(approval.approval_id) is not approval
            or approval.runtime_identity_id != identity.runtime_identity_id
            or approval.lesson_id != memory.lesson.lesson_id
            or approval.content_hash != content_digest(content)
            or approval.source_reference != memory.source_reference
            or approval.session_id != memory.session_id
            or approval.tenant_id != memory.tenant_id
            or approval.owner_id != memory.owner_id
            or approval.retention_policy is not retention_policy
        ):
            raise PermissionError("lesson approval is missing, stale, or scope mismatched")
        provenance = MemoryProvenance(
            memory.source_reference, MemoryOrigin.INFERRED, memory.recorded_at,
            memory.tenant_id, memory.owner_id, memory.session_id, 1.0,
        )
        durable = DurableMemoryRecord(
            memory.lesson.lesson_id, memory.owner_id, memory.tenant_id,
            memory.domain, DurableMemoryType.LESSON, content, content_digest(content),
            "synthetic_test", memory.source_reference, provenance,
            ProvenanceClass.DERIVED_ANALYSIS, 1.0, 0.8, memory.sensitivity,
            memory.recorded_at, memory.recorded_at, None, retention_policy,
            MemoryLifecycle.ACTIVE, 1,
        )
        envelope = seal_memory_content(durable, self._provider)
        del self._approvals[approval.approval_id]
        store.write(MemoryScope(memory.tenant_id, memory.owner_id), envelope)
        return LearnedLessonReceipt(
            durable.memory_id, memory.lesson.outcome_event_id,
            durable.owner_id, durable.tenant_id,
            envelope.payload.key_reference, envelope.payload.key_version,
        )
