"""R94A MEDAR marketing analysis contract tests."""

import pytest

from backend.medar.marketing import MarketingAnalysisRequest, MarketingArea


def test_marketing_contract_supports_all_roadmap_analysis_areas():
    assert tuple(item.value for item in MarketingArea) == (
        "CAMPAIGN", "SEO", "CONTENT", "BRANDING", "COMPETITOR_RESEARCH",
        "FUNNEL", "CONVERSION", "KPI",
    )
    request = MarketingAnalysisRequest(
        "request", "Improve conversion", tuple(MarketingArea), {"conversion": 0.03}, ("source",),
    )
    assert request.action_authority is False


def test_marketing_analysis_cannot_authorize_campaign_action():
    with pytest.raises(ValueError, match="cannot authorize"):
        MarketingAnalysisRequest(
            "request", "goal", (MarketingArea.CAMPAIGN,), {}, (), action_authority=True,
        )
