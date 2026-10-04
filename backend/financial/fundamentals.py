"""Evidence-bound company fundamentals; absent observations remain unknown."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping


FUNDAMENTAL_METRICS = frozenset({
    "revenue", "earnings", "eps", "free_cash_flow", "cash", "debt",
    "gross_margin", "operating_margin", "net_margin", "roic", "revenue_growth",
    "earnings_growth", "shares_outstanding", "price_to_earnings",
    "enterprise_value_to_ebitda", "price_to_free_cash_flow",
})


@dataclass(frozen=True)
class FundamentalObservation:
    value: Decimal
    unit: str
    fiscal_period: str
    source: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise ValueError("fundamental value must be a finite Decimal")
        for name in ("unit", "fiscal_period", "source"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True)
class CompanyFundamentals:
    asset_id: str
    currency: str
    fiscal_period: str
    observations: Mapping[str, FundamentalObservation] = field(default_factory=dict)
    guidance: str | None = None
    guidance_source: str | None = None
    earnings_date: datetime | None = None
    earnings_date_source: str | None = None

    def __post_init__(self) -> None:
        for name in ("asset_id", "currency", "fiscal_period"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if not isinstance(self.observations, Mapping):
            raise TypeError("observations must be a mapping")
        for name, observation in self.observations.items():
            if name not in FUNDAMENTAL_METRICS or not isinstance(observation, FundamentalObservation):
                raise ValueError("unsupported or unevidenced fundamental")
            if observation.fiscal_period != self.fiscal_period:
                raise ValueError("fundamental period mismatch")
        if (self.guidance is None) != (self.guidance_source is None):
            raise ValueError("guidance requires source provenance")
        if self.earnings_date is not None:
            if self.earnings_date.tzinfo is None or self.earnings_date.utcoffset() is None or not self.earnings_date_source:
                raise ValueError("earnings date requires timezone and source")
        elif self.earnings_date_source is not None:
            raise ValueError("earnings date source without date")
        object.__setattr__(self, "observations", MappingProxyType(dict(self.observations)))

    def get(self, metric: str) -> FundamentalObservation | None:
        return self.observations.get(metric)
