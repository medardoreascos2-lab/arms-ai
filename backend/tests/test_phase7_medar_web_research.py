"""R90A MEDAR web research contract tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.web_research import SourceKind, TrustMetadata, WebQuery, WebSource


def test_web_contract_carries_freshness_and_trust_metadata():
    now = datetime.now(timezone.utc)
    trust = TrustMetadata(0.9, SourceKind.PRIMARY, True, False)
    source = WebSource("source-1", "Official source", "https://example.test", now, now, trust)
    query = WebQuery("query-1", "current specification", now, 5)
    assert source.published_at == now
    assert source.fetched_at == now
    assert source.trust.source_kind is SourceKind.PRIMARY
    assert query.max_results == 5


def test_web_query_and_source_require_timezone_aware_freshness():
    with pytest.raises(ValueError, match="timezone-aware"):
        WebQuery("query", "text", datetime.now())
    with pytest.raises(ValueError, match="timezone-aware"):
        WebSource(
            "source", "title", "https://example.test", None, datetime.now(),
            TrustMetadata(0.5, SourceKind.UNKNOWN, False, False),
        )
