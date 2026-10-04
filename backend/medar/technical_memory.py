"""Explicit technical-memory evidence collected in bounded session state."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from backend.medar.memory_candidates import has_secret_like_content


class TechnicalMemoryKind(str, Enum):
    ARCHITECTURE_DECISION = "ARCHITECTURE_DECISION"
    BUG = "BUG"
    ROOT_CAUSE = "ROOT_CAUSE"
    SOLUTION = "SOLUTION"
    TEST = "TEST"
    KNOWN_LIMITATION = "KNOWN_LIMITATION"


@dataclass(frozen=True)
class TechnicalMemoryEntry:
    kind: TechnicalMemoryKind
    content: str = field(repr=False)
    tenant_id: str
    owner_id: str
    session_id: str
    source_reference: str
    observed_at: datetime
    persistence_authorized: bool = False
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, TechnicalMemoryKind):
            raise TypeError("technical memory kind must be explicit")
        if not isinstance(self.content, str) or not self.content.strip() or len(self.content) > 1024:
            raise ValueError("technical content must be bounded")
        if has_secret_like_content(self.content):
            raise PermissionError("secret-like technical content is not retained")
        for name in ("tenant_id", "owner_id", "session_id", "source_reference"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.persistence_authorized or self.execution_authority:
            raise ValueError("technical memory cannot grant persistence or execution")


class TechnicalSessionMemory:
    def __init__(self, tenant_id: str, owner_id: str, session_id: str, *, max_entries: int = 100):
        for name, value in (("tenant_id", tenant_id), ("owner_id", owner_id), ("session_id", session_id)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if type(max_entries) is not int or not 1 <= max_entries <= 1000:
            raise ValueError("max_entries must be 1 to 1000")
        self.tenant_id = tenant_id
        self.owner_id = owner_id
        self.session_id = session_id
        self.max_entries = max_entries
        self._entries: list[TechnicalMemoryEntry] = []

    def add(self, kind: TechnicalMemoryKind, content: str, source_reference: str, *, observed_at: datetime | None = None) -> TechnicalMemoryEntry:
        if len(self._entries) >= self.max_entries:
            raise ValueError("technical session memory capacity exceeded")
        entry = TechnicalMemoryEntry(
            kind, content, self.tenant_id, self.owner_id, self.session_id,
            source_reference, observed_at or datetime.now(timezone.utc),
        )
        if any(existing.kind is entry.kind and existing.source_reference == entry.source_reference for existing in self._entries):
            raise ValueError("technical evidence source already recorded")
        self._entries.append(entry)
        return entry

    def snapshot(self, *, tenant_id: str, owner_id: str, session_id: str) -> tuple[TechnicalMemoryEntry, ...]:
        if (tenant_id, owner_id, session_id) != (self.tenant_id, self.owner_id, self.session_id):
            raise PermissionError("technical memory session scope mismatch")
        return tuple(self._entries)
