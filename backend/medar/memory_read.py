"""Scoped, read-only retrieval contracts for MEDAR memory."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from backend.medar.memory_types import MemoryDomain, MemorySensitivity


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


@dataclass(frozen=True)
class MemoryQuery:
    tenant_id: str
    user_id: str
    query: str
    domains: tuple[MemoryDomain, ...]
    allowed_sensitivity: tuple[MemorySensitivity, ...]
    limit: int = 10

    def __post_init__(self) -> None:
        for name in ("tenant_id", "user_id", "query"):
            _require_text(name, getattr(self, name))
        if not self.domains or any(not isinstance(item, MemoryDomain) for item in self.domains):
            raise ValueError("at least one typed memory domain is required")
        if not self.allowed_sensitivity or any(
            not isinstance(item, MemorySensitivity) for item in self.allowed_sensitivity
        ):
            raise ValueError("at least one typed sensitivity is required")
        if not 1 <= self.limit <= 100:
            raise ValueError("memory result limit must be between 1 and 100")


@dataclass(frozen=True)
class MemoryReadResult:
    memory_id: str
    tenant_id: str
    user_id: str
    domain: MemoryDomain
    sensitivity: MemorySensitivity
    content: str
    source_provenance: str
    confidence: float
    recorded_at: datetime

    def __post_init__(self) -> None:
        for name in ("memory_id", "tenant_id", "user_id", "content", "source_provenance"):
            _require_text(name, getattr(self, name))
        if not isinstance(self.domain, MemoryDomain):
            raise TypeError("domain must be MemoryDomain")
        if not isinstance(self.sensitivity, MemorySensitivity):
            raise TypeError("sensitivity must be MemorySensitivity")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")

    def is_visible_to(self, query: MemoryQuery) -> bool:
        return (
            self.tenant_id == query.tenant_id
            and self.user_id == query.user_id
            and self.domain in query.domains
            and self.sensitivity in query.allowed_sensitivity
        )


class MemoryReader(Protocol):
    def retrieve(self, query: MemoryQuery) -> tuple[MemoryReadResult, ...]: ...
