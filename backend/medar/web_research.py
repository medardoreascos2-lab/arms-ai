"""Provider-neutral, read-only web research contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol


class SourceKind(str, Enum):
    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TrustMetadata:
    authority: float
    source_kind: SourceKind
    citation_complete: bool
    conflicts_reported: bool

    def __post_init__(self) -> None:
        if not 0.0 <= self.authority <= 1.0:
            raise ValueError("authority must be between zero and one")


@dataclass(frozen=True)
class WebQuery:
    query_id: str
    text: str
    requested_at: datetime
    max_results: int = 10

    def __post_init__(self) -> None:
        if not self.query_id.strip() or not self.text.strip():
            raise ValueError("query identity and text are required")
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("requested_at must be timezone-aware")
        if not 1 <= self.max_results <= 50:
            raise ValueError("max_results must be between 1 and 50")


@dataclass(frozen=True)
class WebSource:
    source_id: str
    title: str
    url: str
    published_at: datetime | None
    fetched_at: datetime
    trust: TrustMetadata

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.title.strip() or not self.url.strip():
            raise ValueError("source identity, title, and URL are required")
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        if self.published_at is not None and (
            self.published_at.tzinfo is None or self.published_at.utcoffset() is None
        ):
            raise ValueError("published_at must be timezone-aware when provided")


@dataclass(frozen=True)
class SearchResult:
    query_id: str
    source: WebSource
    snippet: str
    rank: int


@dataclass(frozen=True)
class FetchResult:
    source: WebSource
    content: str
    content_digest: str


@dataclass(frozen=True)
class Citation:
    source_id: str
    locator: str
    supported_claim: str


class WebResearchProvider(Protocol):
    def search(self, query: WebQuery) -> tuple[SearchResult, ...]: ...

    def fetch(self, source: WebSource) -> FetchResult: ...
