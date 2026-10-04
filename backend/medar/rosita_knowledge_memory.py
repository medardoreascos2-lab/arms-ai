"""Encrypted, highly sensitive ROSITA knowledge for local Phase 8 development."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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
from backend.medar.memory_access import MemoryPurpose
from backend.medar.memory_candidates import has_secret_like_content
from backend.medar.memory_encryption_readiness import EncryptionReadiness, assess_encryption_readiness
from backend.medar.memory_provenance import MemoryOrigin, MemoryProvenance
from backend.medar.sqlite_memory_store import MemoryScope
from backend.medar.trusted_runtime_identity import (
    LocalAdminIdentityAuthority, RuntimeMemoryPermission, TrustedRuntimeIdentity,
)


class RositaKnowledgeKind(str, Enum):
    NOTE = "NOTE"
    AUDIO_METADATA = "AUDIO_METADATA"
    VIDEO_METADATA = "VIDEO_METADATA"
    DOCUMENT = "DOCUMENT"
    FAMILY_EXPERIENCE = "FAMILY_EXPERIENCE"
    TRADITIONAL_PRACTICE = "TRADITIONAL_PRACTICE"
    MEDICAL_EVIDENCE_REFERENCE = "MEDICAL_EVIDENCE_REFERENCE"


class RositaProvenanceClass(str, Enum):
    PERSONAL_EXPERIENCE = "PERSONAL_EXPERIENCE"
    TRADITIONAL_PRACTICE = "TRADITIONAL_PRACTICE"
    CLINICAL_EVIDENCE = "CLINICAL_EVIDENCE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class RositaKnowledgeMemory:
    knowledge_id: str
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    kind: RositaKnowledgeKind
    provenance_classification: RositaProvenanceClass
    title: str = field(repr=False)
    content: str = field(repr=False)
    evidence_references: tuple[str, ...] = field(repr=False)
    observed_at: datetime
    domain: DurableMemoryDomain = DurableMemoryDomain.ROSITA
    sensitivity: DurableSensitivity = DurableSensitivity.HIGHLY_SENSITIVE
    user_authorized: bool = True
    local_development_only: bool = True
    external_sharing_authority: bool = False

    def __post_init__(self) -> None:
        for name in (
            "knowledge_id", "tenant_id", "owner_id", "session_id",
            "source_reference", "title", "content",
        ):
            value = getattr(self, name)
            maximum = 4096 if name == "content" else 240
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError(f"{name} must be bounded non-empty text")
        if not isinstance(self.kind, RositaKnowledgeKind) or not isinstance(
            self.provenance_classification, RositaProvenanceClass
        ):
            raise TypeError("ROSITA knowledge kind and provenance must be explicit")
        if not isinstance(self.evidence_references, tuple) or len(self.evidence_references) > 20:
            raise ValueError("evidence references must be a bounded tuple")
        for reference in self.evidence_references:
            if not isinstance(reference, str) or not reference.strip() or len(reference) > 240:
                raise ValueError("evidence references must be bounded non-empty text")
        if has_secret_like_content(self.title) or has_secret_like_content(self.content):
            raise PermissionError("secret-like ROSITA content is not retained")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observation time must be timezone-aware")
        if self.domain is not DurableMemoryDomain.ROSITA or self.sensitivity is not DurableSensitivity.HIGHLY_SENSITIVE:
            raise ValueError("ROSITA classification cannot be weakened")
        if not self.user_authorized or not self.local_development_only or self.external_sharing_authority:
            raise PermissionError("ROSITA memory requires local user authorization and cannot enable sharing")
        if not self.source_reference.startswith("synthetic-test:"):
            raise PermissionError("local ROSITA persistence accepts synthetic sources only")

    def serialized_content(self) -> str:
        return json.dumps({
            "content": self.content,
            "evidence_references": list(self.evidence_references),
            "kind": self.kind.value,
            "provenance_classification": self.provenance_classification.value,
            "title": self.title,
        }, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class RositaKnowledgeApproval:
    approval_id: str
    runtime_identity_id: str
    knowledge_id: str
    content_hash: str
    tenant_id: str
    owner_id: str
    session_id: str
    retention_policy: RetentionPolicy


@dataclass(frozen=True)
class RositaKnowledgeReceipt:
    knowledge_id: str
    tenant_id: str
    owner_id: str
    key_reference: str
    key_version: str
    local_development_only: bool = True
    external_sharing_authorized: bool = False


class EncryptedRositaWriter(Protocol):
    def write(self, scope: MemoryScope, envelope: EncryptedMemoryEnvelope) -> None: ...


class RositaKnowledgeWriteAuthority:
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
            raise PermissionError("ROSITA encryption is not ready")
        self._identity_authority = identity_authority
        self._provider = provider
        self._approvals: dict[str, RositaKnowledgeApproval] = {}

    def _validate(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        record: RositaKnowledgeMemory,
        retention_policy: RetentionPolicy,
    ) -> None:
        self._identity_authority.require_valid(identity)
        if not isinstance(request, BoundMemoryRequest) or not isinstance(record, RositaKnowledgeMemory):
            raise TypeError("bound request and ROSITA record are required")
        if (
            identity.owner_id != request.owner_id or request.owner_id != record.owner_id
            or identity.tenant_id != request.tenant_id or request.tenant_id != record.tenant_id
            or identity.session_id != request.session_id or request.session_id != record.session_id
            or identity.service_id != request.service_id
            or identity.purpose is not request.purpose
        ):
            raise PermissionError("ROSITA identity scope mismatch")
        if identity.purpose is not MemoryPurpose.RESEARCH or RuntimeMemoryPermission.WRITE not in identity.permissions:
            raise PermissionError("ROSITA research write authority is missing")
        if request.claimed_role is not None or request.claimed_permission not in (None, RuntimeMemoryPermission.WRITE):
            raise PermissionError("caller claims cannot grant ROSITA authority")
        if request.domain is not record.domain or request.sensitivity is not record.sensitivity:
            raise PermissionError("ROSITA classification scope mismatch")
        if retention_policy not in (RetentionPolicy.LONG_TERM, RetentionPolicy.MANUAL_REVIEW):
            raise PermissionError("ROSITA retention policy is not approved")

    def approve(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        record: RositaKnowledgeMemory,
        retention_policy: RetentionPolicy,
    ) -> RositaKnowledgeApproval:
        self._validate(identity, request, record, retention_policy)
        approval = RositaKnowledgeApproval(
            token_hex(16), identity.runtime_identity_id, record.knowledge_id,
            content_digest(record.serialized_content()), record.tenant_id,
            record.owner_id, record.session_id, retention_policy,
        )
        self._approvals[approval.approval_id] = approval
        return approval

    def persist(
        self,
        identity: TrustedRuntimeIdentity,
        request: BoundMemoryRequest,
        record: RositaKnowledgeMemory,
        retention_policy: RetentionPolicy,
        approval: RositaKnowledgeApproval,
        store: EncryptedRositaWriter,
    ) -> RositaKnowledgeReceipt:
        self._validate(identity, request, record, retention_policy)
        if not isinstance(approval, RositaKnowledgeApproval) or (
            self._approvals.get(approval.approval_id) is not approval
            or approval.runtime_identity_id != identity.runtime_identity_id
            or approval.knowledge_id != record.knowledge_id
            or approval.content_hash != content_digest(record.serialized_content())
            or approval.tenant_id != record.tenant_id
            or approval.owner_id != record.owner_id
            or approval.session_id != record.session_id
            or approval.retention_policy is not retention_policy
        ):
            raise PermissionError("ROSITA approval is missing, stale, or scope mismatched")
        content = record.serialized_content()
        provenance = MemoryProvenance(
            record.source_reference, MemoryOrigin.OBSERVED, record.observed_at,
            record.tenant_id, record.owner_id, record.session_id, 1.0,
        )
        durable = DurableMemoryRecord(
            record.knowledge_id, record.owner_id, record.tenant_id,
            record.domain, DurableMemoryType.FACT, content, content_digest(content),
            "synthetic_test", record.source_reference, provenance,
            ProvenanceClass.DIRECT_OBSERVATION, 1.0, 0.8, record.sensitivity,
            record.observed_at, record.observed_at, None, retention_policy,
            MemoryLifecycle.ACTIVE, 1,
        )
        envelope = seal_memory_content(durable, self._provider)
        del self._approvals[approval.approval_id]
        store.write(MemoryScope(record.tenant_id, record.owner_id), envelope)
        return RositaKnowledgeReceipt(
            record.knowledge_id, record.tenant_id, record.owner_id,
            envelope.payload.key_reference, envelope.payload.key_version,
        )
