"""Bounded, process-local MEDAR session state with no durable write path."""

from dataclasses import dataclass

from backend.medar.memory_candidates import MemoryCandidate, has_secret_like_content
from backend.medar.memory_evidence_references import CitedMemoryItem


@dataclass(frozen=True)
class TemporarySessionItem:
    content: str
    source_reference: str

    def __post_init__(self) -> None:
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("temporary content is required")
        if not isinstance(self.source_reference, str) or not self.source_reference.strip():
            raise ValueError("temporary source is required")
        if has_secret_like_content(self.content):
            raise PermissionError("secret-like content cannot enter session memory")


@dataclass(frozen=True)
class WorkingMemorySnapshot:
    session_id: str
    tenant_id: str
    owner_id: str
    temporary: tuple[TemporarySessionItem, ...]
    candidate_durable: tuple[MemoryCandidate, ...]
    durable_retrieved: tuple[CitedMemoryItem, ...]
    used_bytes: int
    persistence_performed: bool = False

    def __post_init__(self) -> None:
        if self.persistence_performed:
            raise ValueError("working memory cannot persist content")


class SessionWorkingMemory:
    def __init__(self, session_id: str, tenant_id: str, owner_id: str, *, max_items: int = 100, max_bytes: int = 100_000):
        for name, value in (("session_id", session_id), ("tenant_id", tenant_id), ("owner_id", owner_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        for name, value in (("max_items", max_items), ("max_bytes", max_bytes)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be positive")
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.owner_id = owner_id
        self.max_items = max_items
        self.max_bytes = max_bytes
        self._temporary: list[TemporarySessionItem] = []
        self._candidate_durable: list[MemoryCandidate] = []
        self._durable_retrieved: list[CitedMemoryItem] = []
        self._used_bytes = 0

    def _reserve(self, size: int) -> None:
        count = len(self._temporary) + len(self._candidate_durable) + len(self._durable_retrieved)
        if count >= self.max_items or size > self.max_bytes - self._used_bytes:
            raise ValueError("working memory capacity exceeded")
        self._used_bytes += size

    def add_temporary(self, item: TemporarySessionItem) -> None:
        if not isinstance(item, TemporarySessionItem):
            raise TypeError("temporary item is required")
        self._reserve(len(item.content.encode("utf-8")) + len(item.source_reference.encode("utf-8")))
        self._temporary.append(item)

    def add_candidate(self, candidate: MemoryCandidate) -> None:
        if not isinstance(candidate, MemoryCandidate):
            raise TypeError("memory candidate is required")
        if candidate.tenant_id != self.tenant_id or candidate.owner_id != self.owner_id:
            raise PermissionError("candidate owner scope mismatch")
        if has_secret_like_content(candidate.content):
            raise PermissionError("secret-like candidate cannot enter session memory")
        self._reserve(len(candidate.content.encode("utf-8")) + len(candidate.source_reference.encode("utf-8")))
        self._candidate_durable.append(candidate)

    def add_retrieved(self, item: CitedMemoryItem) -> None:
        if not isinstance(item, CitedMemoryItem):
            raise TypeError("cited memory item is required")
        if item.reference.tenant_id != self.tenant_id or item.reference.owner_id != self.owner_id:
            raise PermissionError("retrieved memory owner scope mismatch")
        if has_secret_like_content(item.content):
            raise PermissionError("secret-like retrieved memory cannot enter session memory")
        self._reserve(len(item.content.encode("utf-8")) + len(item.reference.source_reference.encode("utf-8")))
        self._durable_retrieved.append(item)

    def snapshot(self) -> WorkingMemorySnapshot:
        return WorkingMemorySnapshot(
            self.session_id, self.tenant_id, self.owner_id,
            tuple(self._temporary), tuple(self._candidate_durable),
            tuple(self._durable_retrieved), self._used_bytes,
        )

    def clear(self) -> None:
        self._temporary.clear()
        self._candidate_durable.clear()
        self._durable_retrieved.clear()
        self._used_bytes = 0
