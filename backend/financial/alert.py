"""Advisory financial alert contract with explicit source and priority."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AlertCategory(str, Enum):
    MARKET = "MARKET"
    RISK = "RISK"
    PORTFOLIO = "PORTFOLIO"
    TRADE_BEHAVIOR = "TRADE_BEHAVIOR"
    CRYPTO_ARBITRAGE = "CRYPTO_ARBITRAGE"
    PROP_FIRM_LIMITS = "PROP_FIRM_LIMITS"


class AlertPriority(str, Enum):
    INFO = "INFO"
    WATCH = "WATCH"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class FinancialAlert:
    alert_id: str
    category: AlertCategory
    priority: AlertPriority
    message: str
    source_reference: str
    observed_at: datetime
    asset_id: str | None = None
    advisory_only: bool = True
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if not self.alert_id.strip() or not self.message.strip() or not self.source_reference.strip():
            raise ValueError("alert identity, message and source are required")
        if not isinstance(self.category, AlertCategory) or not isinstance(self.priority, AlertPriority):
            raise TypeError("alert category and priority must be explicit")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("alert time must be timezone-aware")
        if not self.advisory_only or self.execution_authority:
            raise ValueError("alert cannot authorize execution")
