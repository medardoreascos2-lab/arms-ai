"""Local, content-free financial feature usage events."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class FinancialFeature(str, Enum):
    COMPANY_ANALYSIS = "COMPANY_ANALYSIS"
    PORTFOLIO_GUARDIAN = "PORTFOLIO_GUARDIAN"
    ARBITRAGE_RADAR = "ARBITRAGE_RADAR"
    TRADING_COACH = "TRADING_COACH"
    SHADOW_MEDAR = "SHADOW_MEDAR"


@dataclass(frozen=True, slots=True)
class FeatureUsageEvent:
    feature: FinancialFeature
    day: date
    local_only: bool = True
    contains_financial_content: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.feature, FinancialFeature) or not isinstance(self.day, date):
            raise ValueError("feature and day must be explicit")
        if not self.local_only or self.contains_financial_content:
            raise ValueError("feature usage cannot contain or send financial content")


@dataclass(frozen=True)
class FeatureUsageSummary:
    day: date
    counts: Mapping[FinancialFeature, int]
    local_only: bool = True


def aggregate_feature_usage(events: tuple[FeatureUsageEvent, ...], day: date) -> FeatureUsageSummary:
    counts = {feature: 0 for feature in FinancialFeature}
    for event in events:
        if event.day == day:
            counts[event.feature] += 1
    return FeatureUsageSummary(day, MappingProxyType(counts))
