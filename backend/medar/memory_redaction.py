"""Allowlisted MEDAR memory event metadata with no raw content or identifiers."""

from dataclasses import dataclass
from hashlib import sha256

from backend.medar.durable_memory_record import DurableMemoryRecord


@dataclass(frozen=True)
class RedactedMemoryEvent:
    event_type: str
    memory_id_digest: str
    owner_id_digest: str
    tenant_id_digest: str
    domain: str
    status: str
    sensitivity: str
    raw_content_stored: bool = False

    def __post_init__(self) -> None:
        if self.raw_content_stored:
            raise ValueError("memory logs cannot contain raw content")


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def redacted_memory_event(record: DurableMemoryRecord, event_type: str) -> RedactedMemoryEvent:
    if event_type not in {"WRITE", "READ", "SEARCH_HIT", "SUPERSEDE", "EXPIRE", "RETRACT", "DENY"}:
        raise ValueError("unsupported memory event type")
    return RedactedMemoryEvent(
        event_type,
        _digest(record.memory_id),
        _digest(record.owner_id),
        _digest(record.tenant_id),
        record.domain.value,
        record.status.value,
        record.sensitivity.value,
    )
