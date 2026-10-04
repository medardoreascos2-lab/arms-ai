"""F108A: future research requests contain no web or trading action."""

from datetime import datetime, timedelta, timezone

import pytest

from backend.financial.research_request import FinancialResearchRequest, ResearchTopic

NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def test_research_request_is_read_only_contract():
    request = FinancialResearchRequest(
        "synthetic:r1", ResearchTopic.FILINGS, "AAPL filing", NOW,
        timedelta(days=1), "NASDAQ:AAPL",
    )
    assert request.analysis_only
    assert not request.external_action_authority
    assert not hasattr(request, "fetch")


def test_external_authority_cannot_be_set():
    with pytest.raises(ValueError, match="authority"):
        FinancialResearchRequest("r", ResearchTopic.NEWS, "query", NOW,
                                 timedelta(hours=1), external_action_authority=True)
