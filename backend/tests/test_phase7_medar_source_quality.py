"""R90B MEDAR source quality model tests."""

from datetime import datetime, timedelta, timezone

from backend.medar.source_quality import rank_source
from backend.medar.web_research import SourceKind, TrustMetadata, WebSource


def _source(*, kind=SourceKind.PRIMARY, conflict=False, complete=True, age_days=1):
    now = datetime(2026, 1, 10, tzinfo=timezone.utc)
    source = WebSource(
        "source", "Title", "https://example.test", now - timedelta(days=age_days), now,
        TrustMetadata(0.9, kind, complete, conflict),
    )
    return source, now


def test_quality_uses_authority_freshness_primary_conflict_and_citation_completeness():
    strong, now = _source()
    weak, _ = _source(kind=SourceKind.SECONDARY, conflict=True, complete=False, age_days=365)
    strong_rank = rank_source(strong, now=now)
    weak_rank = rank_source(weak, now=now)
    assert strong_rank.score > weak_rank.score
    assert strong_rank.is_primary is True
    assert strong_rank.citation_complete is True
    assert weak_rank.has_conflict is True


def test_ranking_never_claims_absolute_truth():
    source, now = _source()
    assert rank_source(source, now=now).absolute_truth is False
