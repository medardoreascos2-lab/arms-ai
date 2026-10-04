"""Financial research provenance and freshness over untrusted source data."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from backend.financial.research_request import FinancialResearchRequest


class SourceKind(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"


class SourceFreshness(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    FUTURE = "FUTURE"


@dataclass(frozen=True)
class ResearchSource:
    reference: str
    published_at: datetime
    kind: SourceKind
    conflicts_with: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("source reference is required")
        if self.published_at.tzinfo is None or self.published_at.utcoffset() is None:
            raise ValueError("source timestamp must be timezone-aware")
        if not isinstance(self.kind, SourceKind):
            raise TypeError("source kind must be explicit")
        if self.reference in self.conflicts_with or len(set(self.conflicts_with)) != len(self.conflicts_with):
            raise ValueError("source conflict references must be distinct")
        object.__setattr__(self, "conflicts_with", tuple(self.conflicts_with))

    def freshness_for(self, request: FinancialResearchRequest) -> SourceFreshness:
        age = request.requested_at - self.published_at
        if age.total_seconds() < 0:
            return SourceFreshness.FUTURE
        if age > request.maximum_age:
            return SourceFreshness.STALE
        return SourceFreshness.FRESH


@dataclass(frozen=True)
class ResearchProvenance:
    reference: str
    published_at: datetime
    kind: SourceKind
    freshness: SourceFreshness
    conflicts_with: tuple[str, ...]


@dataclass(frozen=True)
class FinancialResearchOutput:
    request_id: str
    statement: str
    provenance: tuple[ResearchProvenance, ...]
    conflict: bool
    analysis_only: bool = True
    external_action_authority: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.statement.strip() or not self.provenance:
            raise ValueError("research output requires statement and provenance")
        if not self.analysis_only or self.external_action_authority:
            raise ValueError("research output cannot grant authority")


def build_research_output(
    request: FinancialResearchRequest,
    statement: str,
    sources: tuple[ResearchSource, ...],
) -> FinancialResearchOutput:
    if not sources or len({source.reference for source in sources}) != len(sources):
        raise ValueError("distinct sources are required")
    known = {source.reference for source in sources}
    if any(ref not in known for source in sources for ref in source.conflicts_with):
        raise ValueError("conflict reference must identify a supplied source")
    provenance = tuple(
        ResearchProvenance(source.reference, source.published_at, source.kind,
                           source.freshness_for(request), source.conflicts_with)
        for source in sources
    )
    return FinancialResearchOutput(
        request.request_id, statement, provenance,
        any(source.conflicts_with for source in sources),
    )
