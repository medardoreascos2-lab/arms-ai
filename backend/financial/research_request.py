"""Read-only contract for future financial research providers."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ResearchTopic(str, Enum):
    NEWS = "NEWS"
    EARNINGS = "EARNINGS"
    MACRO = "MACRO"
    FILINGS = "FILINGS"
    CRYPTO_EVENTS = "CRYPTO_EVENTS"


@dataclass(frozen=True)
class FinancialResearchRequest:
    request_id: str
    topic: ResearchTopic
    query: str
    requested_at: datetime
    maximum_age: timedelta
    asset_id: str | None = None
    analysis_only: bool = True
    external_action_authority: bool = False

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.query.strip():
            raise ValueError("research request identity and query are required")
        if not isinstance(self.topic, ResearchTopic):
            raise TypeError("research topic must be explicit")
        if self.requested_at.tzinfo is None or self.requested_at.utcoffset() is None:
            raise ValueError("request time must be timezone-aware")
        if not isinstance(self.maximum_age, timedelta) or self.maximum_age <= timedelta(0):
            raise ValueError("maximum age must be positive")
        if self.asset_id is not None and not self.asset_id.strip():
            raise ValueError("asset_id must be nonblank when present")
        if not self.analysis_only or self.external_action_authority:
            raise ValueError("research request cannot grant external authority")
