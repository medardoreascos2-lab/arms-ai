"""Analysis seam for crypto spot, perpetual and dated futures basis."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum


class CryptoMarketKind(str, Enum):
    SPOT = "SPOT"
    PERPETUAL = "PERPETUAL"
    DATED_FUTURE = "DATED_FUTURE"


@dataclass(frozen=True)
class BasisQuote:
    asset_id: str
    base: str
    quote: str
    kind: CryptoMarketKind
    price: Decimal
    timestamp: datetime
    source: str
    expiry: datetime | None = None
    funding_rate_per_interval: Decimal | None = None

    def __post_init__(self) -> None:
        if not all((self.asset_id, self.base, self.quote, self.source)):
            raise ValueError("basis quote identity and source are required")
        if not isinstance(self.kind, CryptoMarketKind):
            raise TypeError("market kind must be explicit")
        if not isinstance(self.price, Decimal) or not self.price.is_finite() or self.price <= 0:
            raise ValueError("basis price must be positive and finite")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("basis timestamp must be timezone-aware")
        if self.kind is CryptoMarketKind.DATED_FUTURE:
            if self.expiry is None or self.expiry.tzinfo is None or self.expiry <= self.timestamp:
                raise ValueError("dated future requires a future expiry")
        elif self.expiry is not None:
            raise ValueError("only dated futures may have expiry")
        if self.funding_rate_per_interval is not None:
            if self.kind is not CryptoMarketKind.PERPETUAL or not isinstance(self.funding_rate_per_interval, Decimal) or not self.funding_rate_per_interval.is_finite():
                raise ValueError("funding rate requires a perpetual quote")


@dataclass(frozen=True)
class BasisAnalysis:
    spot_asset_id: str
    derivative_asset_id: str
    basis_quote: Decimal
    basis_fraction: Decimal
    funding_rate_per_interval: Decimal | None
    expiry: datetime | None
    sources: tuple[str, str]
    analysis_only: bool = True


def analyze_basis(spot: BasisQuote, derivative: BasisQuote, now: datetime, maximum_age: timedelta) -> BasisAnalysis:
    if spot.kind is not CryptoMarketKind.SPOT or derivative.kind is CryptoMarketKind.SPOT:
        raise ValueError("spot and derivative quotes are required")
    if (spot.base, spot.quote) != (derivative.base, derivative.quote):
        raise ValueError("basis instruments must share base and quote")
    if now.tzinfo is None or now.utcoffset() is None or maximum_age <= timedelta(0):
        raise ValueError("valid now and maximum age are required")
    if any(now - item.timestamp < timedelta(0) or now - item.timestamp > maximum_age for item in (spot, derivative)):
        raise ValueError("basis quotes must be fresh")
    basis = derivative.price - spot.price
    return BasisAnalysis(
        spot.asset_id, derivative.asset_id, basis, basis / spot.price,
        derivative.funding_rate_per_interval, derivative.expiry,
        (spot.source, derivative.source),
    )
