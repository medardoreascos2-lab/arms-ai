"""Within-venue triangular arbitrage analysis using supplied conversion legs."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True)
class ConversionLeg:
    venue_id: str
    from_asset: str
    to_asset: str
    rate: Decimal
    fee_rate: Decimal
    slippage_rate: Decimal
    available_input: Decimal
    timestamp: datetime
    source: str

    def __post_init__(self) -> None:
        if not all((self.venue_id, self.from_asset, self.to_asset, self.source)) or self.from_asset == self.to_asset:
            raise ValueError("conversion identity and source are required")
        for name in ("rate", "available_input"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        for name in ("fee_rate", "slippage_rate"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or not 0 <= value < 1:
                raise ValueError(f"{name} must be a finite fraction")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")


@dataclass(frozen=True)
class TriangularResult:
    venue_id: str
    start_asset: str
    start_amount: Decimal
    gross_end_amount: Decimal
    net_end_amount: Decimal
    net_edge: Decimal
    sources: tuple[str, ...]
    analysis_only: bool = True


def analyze_triangular(
    legs: tuple[ConversionLeg, ConversionLeg, ConversionLeg],
    start_amount: Decimal,
    now: datetime,
    maximum_age: timedelta,
) -> TriangularResult:
    if len(legs) != 3 or len({leg.venue_id for leg in legs}) != 1:
        raise ValueError("three legs on one venue are required")
    if not (legs[0].to_asset == legs[1].from_asset
            and legs[1].to_asset == legs[2].from_asset
            and legs[2].to_asset == legs[0].from_asset):
        raise ValueError("triangular path must close without asset mismatch")
    if not isinstance(start_amount, Decimal) or not start_amount.is_finite() or start_amount <= 0:
        raise ValueError("start amount must be positive and finite")
    if now.tzinfo is None or now.utcoffset() is None or maximum_age <= timedelta(0):
        raise ValueError("valid now and maximum age are required")
    gross = start_amount
    net = start_amount
    for leg in legs:
        age = now - leg.timestamp
        if age < timedelta(0) or age > maximum_age:
            raise ValueError("all conversion legs must be fresh")
        if net > leg.available_input:
            raise ValueError("insufficient leg liquidity")
        gross *= leg.rate
        net *= leg.rate * (1 - leg.fee_rate) * (1 - leg.slippage_rate)
    return TriangularResult(
        legs[0].venue_id, legs[0].from_asset, start_amount, gross, net,
        net - start_amount, tuple(leg.source for leg in legs),
    )
