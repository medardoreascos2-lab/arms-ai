"""ETF holdings and risk inputs with explicit coverage and unknowns."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class EtfHolding:
    asset_id: str
    weight: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.asset_id, str) or not self.asset_id.strip():
            raise ValueError("holding asset_id is required")
        if not isinstance(self.weight, Decimal) or not self.weight.is_finite() or not 0 <= self.weight <= 1:
            raise ValueError("holding weight must be within zero and one")


@dataclass(frozen=True)
class EtfIntelligence:
    asset_id: str
    source: str
    observed_at: datetime
    holdings: tuple[EtfHolding, ...] = ()
    sector_exposure: Mapping[str, Decimal] = field(default_factory=dict)
    expense_ratio: Decimal | None = None
    average_daily_volume: Decimal | None = None
    tracking_error: Decimal | None = None
    benchmark_correlation: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or not self.source.strip():
            raise ValueError("ETF identity and source are required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if len({h.asset_id for h in self.holdings}) != len(self.holdings):
            raise ValueError("duplicate ETF holding")
        if sum((h.weight for h in self.holdings), Decimal(0)) > 1:
            raise ValueError("ETF holdings exceed full weight")
        if any(
            not isinstance(k, str) or not k.strip() or not isinstance(v, Decimal)
            or not v.is_finite() or not 0 <= v <= 1
            for k, v in self.sector_exposure.items()
        ):
            raise ValueError("invalid sector exposure")
        if sum(self.sector_exposure.values(), Decimal(0)) > 1:
            raise ValueError("sector exposure exceeds full weight")
        for name in ("expense_ratio", "average_daily_volume", "tracking_error"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite() or value < 0
            ):
                raise ValueError(f"{name} must be nonnegative and finite")
        if self.benchmark_correlation is not None and (
            not isinstance(self.benchmark_correlation, Decimal)
            or not self.benchmark_correlation.is_finite()
            or not -1 <= self.benchmark_correlation <= 1
        ):
            raise ValueError("benchmark_correlation must be between -1 and 1")
        object.__setattr__(self, "holdings", tuple(self.holdings))
        object.__setattr__(self, "sector_exposure", MappingProxyType(dict(self.sector_exposure)))

    @property
    def holdings_coverage(self) -> Decimal:
        return sum((h.weight for h in self.holdings), Decimal(0))

    @property
    def known_top_holding_weight(self) -> Decimal | None:
        return max((h.weight for h in self.holdings), default=None)
