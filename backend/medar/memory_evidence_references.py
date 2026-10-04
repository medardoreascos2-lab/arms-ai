"""Traceable, revalidated memory context entries for MEDAR cognition."""

from dataclasses import dataclass

from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_access import AuthorizedMemoryStore, MemoryAccessContext, authorize_memory_access
from backend.medar.memory_context_budget import MemoryContextSelection
from backend.medar.memory_provenance import MemoryProvenance


@dataclass(frozen=True)
class MemoryEvidenceReference:
    memory_id: str
    version: int
    content_hash: str
    tenant_id: str
    owner_id: str
    domain: DurableMemoryDomain
    sensitivity: DurableSensitivity
    source_type: str
    source_reference: str
    provenance: MemoryProvenance

    def __post_init__(self) -> None:
        if not self.memory_id or not self.source_reference or not self.content_hash:
            raise ValueError("memory citation requires identity, source, and content hash")
        if self.provenance.tenant_id != self.tenant_id or self.provenance.user_id != self.owner_id:
            raise ValueError("memory citation provenance must match owner scope")


@dataclass(frozen=True)
class CitedMemoryItem:
    content: str
    reference: MemoryEvidenceReference
    relevance_score: float
    reserved_tokens: int

    def __post_init__(self) -> None:
        if not self.content.strip() or not 0 <= self.relevance_score <= 1 or self.reserved_tokens < 1:
            raise ValueError("cited memory requires bounded content and relevance")


@dataclass(frozen=True)
class CitedMemoryContext:
    items: tuple[CitedMemoryItem, ...]
    reserved_tokens: int
    persistence_performed: bool = False
    external_call_performed: bool = False

    def __post_init__(self) -> None:
        if self.persistence_performed or self.external_call_performed:
            raise ValueError("cited context cannot write memory or call external services")
        if self.reserved_tokens != sum(item.reserved_tokens for item in self.items):
            raise ValueError("cited context reservation mismatch")


def build_cited_memory_context(
    selection: MemoryContextSelection,
    store: AuthorizedMemoryStore,
    contexts: tuple[MemoryAccessContext, ...],
) -> CitedMemoryContext:
    if not isinstance(selection, MemoryContextSelection) or not isinstance(store, AuthorizedMemoryStore):
        raise TypeError("budgeted selection and authorized store are required")
    if not isinstance(contexts, tuple) or not contexts:
        raise ValueError("at least one access context is required")
    owner = (contexts[0].tenant_id, contexts[0].owner_id)
    if any((context.tenant_id, context.owner_id) != owner for context in contexts):
        raise PermissionError("cited context cannot combine owner scopes")
    if len({context.domain for context in contexts}) != len(contexts):
        raise ValueError("cited context domains must be unique")
    for context in contexts:
        authorize_memory_access(context, "read")
    by_domain = {context.domain: context for context in contexts}
    items: list[CitedMemoryItem] = []
    seen: set[tuple[DurableMemoryDomain, str]] = set()
    for selected in selection.selected:
        evidence = selected.evidence
        record = evidence.record
        context = by_domain.get(record.domain)
        if context is None or context.sensitivity is not record.sensitivity:
            raise PermissionError("selected memory is outside the authorized context")
        if record.sensitivity not in (DurableSensitivity.PUBLIC, DurableSensitivity.INTERNAL):
            raise PermissionError("sensitive memory context is unavailable")
        current = store.get(context, record.memory_id)
        if current is None or (
            current.version != record.version
            or current.content_hash != record.content_hash
            or current.source_reference != record.source_reference
            or current.provenance != record.provenance
        ):
            raise ValueError("selected memory changed before context construction")
        identity = (record.domain, record.memory_id)
        if identity in seen:
            raise ValueError("duplicate memory citation")
        seen.add(identity)
        reference = MemoryEvidenceReference(
            current.memory_id, current.version, current.content_hash,
            current.tenant_id, current.owner_id, current.domain, current.sensitivity,
            current.source_type, current.source_reference, current.provenance,
        )
        items.append(CitedMemoryItem(current.content, reference, evidence.total_score, selected.reserved_tokens))
    if sum(item.reserved_tokens for item in items) != selection.reserved_tokens:
        raise ValueError("selection reservation mismatch")
    return CitedMemoryContext(tuple(items), selection.reserved_tokens)
