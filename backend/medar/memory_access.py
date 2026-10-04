"""Explicit MEDAR memory access policy for trusted caller context.

The caller must bind requester identity from authenticated runtime state. This
module cannot authenticate identities supplied to it and is not yet wired to
an API or the Phase 7 cognitive core.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableMemoryRecord, DurableSensitivity, MemoryLifecycle
from backend.medar.sqlite_memory_store import MemoryScope, MemoryStore


class MemoryPurpose(str, Enum):
    PERSONALIZATION = "PERSONALIZATION"
    TECHNICAL_ASSISTANCE = "TECHNICAL_ASSISTANCE"
    FINANCIAL_ANALYSIS = "FINANCIAL_ANALYSIS"
    BUSINESS_ANALYSIS = "BUSINESS_ANALYSIS"
    RESEARCH = "RESEARCH"
    AUDIT = "AUDIT"


class MemoryAgentPermission(str, Enum):
    NONE = "NONE"
    READ = "READ"
    WRITE = "WRITE"


_PURPOSE_DOMAINS = {
    MemoryPurpose.PERSONALIZATION: frozenset({
        DurableMemoryDomain.PERSONAL, DurableMemoryDomain.PREFERENCES,
        DurableMemoryDomain.LIFE, DurableMemoryDomain.CAREER,
    }),
    MemoryPurpose.TECHNICAL_ASSISTANCE: frozenset({
        DurableMemoryDomain.TECHNICAL, DurableMemoryDomain.CODING,
        DurableMemoryDomain.TOOL, DurableMemoryDomain.MODEL_PERFORMANCE,
    }),
    MemoryPurpose.FINANCIAL_ANALYSIS: frozenset({
        DurableMemoryDomain.TRADING, DurableMemoryDomain.NQ, DurableMemoryDomain.MNQ,
        DurableMemoryDomain.FINANCIAL, DurableMemoryDomain.PORTFOLIO,
        DurableMemoryDomain.CRYPTO, DurableMemoryDomain.CRYPTO_ARBITRAGE,
    }),
    MemoryPurpose.BUSINESS_ANALYSIS: frozenset({
        DurableMemoryDomain.BUSINESS, DurableMemoryDomain.MARKETING,
        DurableMemoryDomain.DECISION_JOURNAL,
    }),
    MemoryPurpose.RESEARCH: frozenset({
        DurableMemoryDomain.RESEARCH, DurableMemoryDomain.SEMANTIC,
        DurableMemoryDomain.EPISODIC, DurableMemoryDomain.ROSITA,
    }),
    MemoryPurpose.AUDIT: frozenset(DurableMemoryDomain),
}


@dataclass(frozen=True)
class MemoryAccessContext:
    requester_id: str
    requester_tenant_id: str
    owner_id: str
    tenant_id: str
    domain: DurableMemoryDomain
    sensitivity: DurableSensitivity
    purpose: MemoryPurpose
    permission: MemoryAgentPermission
    persistence_approved: bool = False

    def __post_init__(self) -> None:
        for field in ("requester_id", "requester_tenant_id", "owner_id", "tenant_id"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} is required")
        if not isinstance(self.domain, DurableMemoryDomain) or not isinstance(self.sensitivity, DurableSensitivity):
            raise TypeError("memory domain and sensitivity must be typed")
        if not isinstance(self.purpose, MemoryPurpose) or not isinstance(self.permission, MemoryAgentPermission):
            raise TypeError("memory purpose and permission must be typed")
        if not isinstance(self.persistence_approved, bool):
            raise TypeError("persistence_approved must be boolean")


def authorize_memory_access(context: MemoryAccessContext, operation: str) -> None:
    if context.requester_id != context.owner_id or context.requester_tenant_id != context.tenant_id:
        raise PermissionError("cross-user or cross-tenant memory access denied")
    if context.domain not in _PURPOSE_DOMAINS[context.purpose]:
        raise PermissionError("memory purpose does not permit domain")
    if context.sensitivity in (DurableSensitivity.PERSONAL, DurableSensitivity.SENSITIVE, DurableSensitivity.HIGHLY_SENSITIVE):
        raise PermissionError("sensitive memory unavailable until production encryption is validated")
    if operation == "read":
        if context.permission not in (MemoryAgentPermission.READ, MemoryAgentPermission.WRITE):
            raise PermissionError("memory read permission missing")
    elif operation == "write":
        if context.permission is not MemoryAgentPermission.WRITE or not context.persistence_approved:
            raise PermissionError("memory write approval or permission missing")
    else:
        raise ValueError("unsupported memory operation")


class AuthorizedMemoryStore:
    """Policy-checked read/write facade over a store; no execution authority."""

    def __init__(self, store: MemoryStore):
        self._store = store

    def get(self, context: MemoryAccessContext, memory_id: str) -> DurableMemoryRecord | None:
        authorize_memory_access(context, "read")
        record = self._store.get(MemoryScope(context.tenant_id, context.owner_id), memory_id)
        if record is not None:
            self._verify_record(context, record)
            if context.purpose is not MemoryPurpose.AUDIT and (
                record.status is not MemoryLifecycle.ACTIVE
                or (record.expires_at is not None and record.expires_at <= datetime.now(timezone.utc))
            ):
                return None
        return record

    def search(self, context: MemoryAccessContext, query: str, limit: int = 10) -> tuple[DurableMemoryRecord, ...]:
        authorize_memory_access(context, "read")
        records = self._store.search(MemoryScope(context.tenant_id, context.owner_id), query, (context.domain,), limit)
        for record in records:
            self._verify_record(context, record)
            if record.status is not MemoryLifecycle.ACTIVE or (
                record.expires_at is not None and record.expires_at <= datetime.now(timezone.utc)
            ):
                raise PermissionError("store returned inactive memory to normal retrieval")
        return records

    def write(self, context: MemoryAccessContext, record: DurableMemoryRecord) -> None:
        authorize_memory_access(context, "write")
        self._verify_record(context, record)
        self._store.write(MemoryScope(context.tenant_id, context.owner_id), record)

    @staticmethod
    def _verify_record(context: MemoryAccessContext, record: DurableMemoryRecord) -> None:
        if (
            record.tenant_id != context.tenant_id
            or record.owner_id != context.owner_id
            or record.domain is not context.domain
            or record.sensitivity is not context.sensitivity
        ):
            raise PermissionError("stored memory scope or classification differs from access scope")
