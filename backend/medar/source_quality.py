"""Heuristic source quality ranking that never claims absolute truth."""

from dataclasses import dataclass
from datetime import datetime

from backend.medar.web_research import SourceKind, WebSource


@dataclass(frozen=True)
class SourceQuality:
    source_id: str
    score: float
    authority: float
    freshness: float
    is_primary: bool
    has_conflict: bool
    citation_complete: bool
    absolute_truth: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("quality score must be between zero and one")
        if self.absolute_truth:
            raise ValueError("source ranking cannot establish absolute truth")


def rank_source(source: WebSource, *, now: datetime) -> SourceQuality:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    reference = source.published_at or source.fetched_at
    age_days = max(0.0, (now - reference).total_seconds() / 86400.0)
    freshness = max(0.0, 1.0 - min(age_days, 365.0) / 365.0)
    trust = source.trust
    is_primary = trust.source_kind is SourceKind.PRIMARY
    score = (
        trust.authority * 0.35
        + freshness * 0.25
        + (0.15 if is_primary else 0.0)
        + (0.0 if trust.conflicts_reported else 0.15)
        + (0.10 if trust.citation_complete else 0.0)
    )
    return SourceQuality(
        source.source_id,
        round(score, 6),
        trust.authority,
        round(freshness, 6),
        is_primary,
        trust.conflicts_reported,
        trust.citation_complete,
    )
