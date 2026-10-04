"""Reviewable memory consolidation proposals that retain every source link."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.medar.durable_memory_record import (
    DurableMemoryDomain, DurableMemoryRecord, MemoryLifecycle,
)
from backend.medar.memory_candidates import has_secret_like_content


@dataclass(frozen=True)
class ConsolidationSource:
    memory_id: str
    source_reference: str
    version: int
    content_hash: str


@dataclass(frozen=True)
class MemoryConsolidationProposal:
    proposal_id: str
    tenant_id: str
    owner_id: str
    domain: DurableMemoryDomain
    summary: str = field(repr=False)
    sources: tuple[ConsolidationSource, ...]
    created_at: datetime
    persistence_authority: bool = False
    deletion_authority: bool = False
    supersession_authority: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.domain, DurableMemoryDomain) or len(self.sources) < 2:
            raise ValueError("consolidation proposal requires a typed domain and source links")
        if any((self.persistence_authority, self.deletion_authority, self.supersession_authority)):
            raise ValueError("consolidation proposal cannot authorize memory mutation")


def propose_memory_consolidation(
    records: tuple[DurableMemoryRecord, ...],
    *,
    proposal_id: str,
    summary: str,
    created_at: datetime,
    minimum_age: timedelta = timedelta(0),
) -> MemoryConsolidationProposal:
    if not isinstance(records, tuple) or len(records) < 2 or any(not isinstance(item, DurableMemoryRecord) for item in records):
        raise ValueError("consolidation requires at least two typed memory records")
    if not isinstance(proposal_id, str) or not proposal_id.strip() or len(proposal_id) > 240:
        raise ValueError("consolidation proposal ID must be bounded text")
    if not isinstance(summary, str) or not summary.strip() or len(summary) > 2048:
        raise ValueError("consolidation summary must be bounded explicit text")
    if has_secret_like_content(summary):
        raise PermissionError("secret-like consolidation summary is not retained")
    if not isinstance(created_at, datetime) or created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("consolidation time must be timezone-aware")
    if not isinstance(minimum_age, timedelta) or minimum_age < timedelta(0):
        raise ValueError("minimum consolidation age cannot be negative")
    first = records[0]
    if any(
        record.tenant_id != first.tenant_id or record.owner_id != first.owner_id
        or record.domain is not first.domain or record.sensitivity is not first.sensitivity
        for record in records
    ):
        raise PermissionError("consolidation records must share owner, tenant, domain, and sensitivity")
    if len({record.memory_id for record in records}) != len(records):
        raise ValueError("consolidation records must have unique memory IDs")
    if any(record.status is not MemoryLifecycle.ACTIVE for record in records):
        raise PermissionError("only active memories may be proposed for consolidation")
    if any(record.created_at > created_at or created_at - record.created_at < minimum_age for record in records):
        raise PermissionError("memory has not reached the periodic consolidation age")
    sources = tuple(sorted(
        (
            ConsolidationSource(
                record.memory_id, record.source_reference,
                record.version, record.content_hash,
            )
            for record in records
        ),
        key=lambda item: (item.memory_id, item.version),
    ))
    return MemoryConsolidationProposal(
        proposal_id, first.tenant_id, first.owner_id, first.domain,
        " ".join(summary.split()), sources, created_at,
    )
