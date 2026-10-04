"""Sensitive decision-journal foundation; durable writes remain fail-closed."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from backend.medar.decision_journal import DecisionJournalEntry
from backend.medar.durable_memory_record import DurableMemoryDomain, DurableSensitivity
from backend.medar.memory_candidates import has_secret_like_content


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
    session_only: bool = True
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
        if not self.session_only or self.persistence_authorized or self.execution_authority:
            raise ValueError("journal cannot claim durable write or execution authority")


class JournalWriter(Protocol):
    def write(self, record: DecisionJournalMemory) -> None: ...


def persist_decision_journal(record: DecisionJournalMemory, writer: JournalWriter) -> None:
    """Block all sensitive durable writes until production encryption is approved."""
    if not isinstance(record, DecisionJournalMemory):
        raise TypeError("validated decision journal memory is required")
    raise PermissionError("sensitive decision journal persistence requires approved production encryption")
