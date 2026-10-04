"""R90C MEDAR multi-source research synthesis tests."""

from datetime import datetime, timezone

import pytest

from backend.medar.agents import WebResearchAgent
from backend.medar.research_synthesis import ResearchFinding
from backend.medar.web_research import SourceKind, TrustMetadata, WebSource


def _source(source_id):
    now = datetime.now(timezone.utc)
    return WebSource(
        source_id, source_id, f"https://{source_id}.test", now, now,
        TrustMetadata(0.8, SourceKind.PRIMARY, True, False),
    )


def test_web_research_agent_combines_sources_and_preserves_disagreement():
    sources = (_source("a"), _source("b"))
    findings = (ResearchFinding("a", "Claim A"), ResearchFinding("b", "Claim B"))
    result = WebResearchAgent().synthesize(findings, sources)
    assert result.sources == sources
    assert result.findings == findings
    assert result.disagreements == ("Claim A", "Claim B")
    assert result.sufficient is True


def test_untraceable_finding_is_rejected():
    with pytest.raises(ValueError, match="provided source"):
        WebResearchAgent().synthesize((ResearchFinding("missing", "claim"),), (_source("a"),))
