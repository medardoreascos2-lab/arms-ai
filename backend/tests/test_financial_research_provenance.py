"""F108B: research output carries source time, type, freshness and conflict."""

from datetime import datetime, timedelta, timezone

from backend.financial.research_provenance import (
    ResearchSource, SourceFreshness, SourceKind, build_research_output,
)
from backend.financial.research_request import FinancialResearchRequest, ResearchTopic

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_source_provenance_marks_stale_and_conflicting_evidence():
    request = FinancialResearchRequest("synthetic:r1", ResearchTopic.NEWS, "test",
                                       NOW, timedelta(hours=1))
    sources = (
        ResearchSource("synthetic:primary", NOW - timedelta(minutes=5), SourceKind.PRIMARY,
                       ("synthetic:secondary",)),
        ResearchSource("synthetic:secondary", NOW - timedelta(days=1), SourceKind.SECONDARY),
    )
    output = build_research_output(request, "untrusted observation", sources)
    assert output.provenance[0].freshness is SourceFreshness.FRESH
    assert output.provenance[1].freshness is SourceFreshness.STALE
    assert output.conflict
    assert not output.external_action_authority
