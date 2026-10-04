"""Advisory marketing analysis contract for future integrations."""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class MarketingArea(str, Enum):
    CAMPAIGN = "CAMPAIGN"
    SEO = "SEO"
    CONTENT = "CONTENT"
    BRANDING = "BRANDING"
    COMPETITOR_RESEARCH = "COMPETITOR_RESEARCH"
    FUNNEL = "FUNNEL"
    CONVERSION = "CONVERSION"
    KPI = "KPI"


@dataclass(frozen=True)
class MarketingAnalysisRequest:
    request_id: str
    goal: str
    areas: tuple[MarketingArea, ...]
    kpis: Mapping[str, float]
    evidence_ids: tuple[str, ...]
    action_authority: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.goal.strip() or not self.areas:
            raise ValueError("marketing request identity, goal, and areas are required")
        if any(not isinstance(area, MarketingArea) for area in self.areas):
            raise TypeError("marketing areas must be typed")
        if self.action_authority:
            raise ValueError("marketing analysis cannot authorize campaign actions")
