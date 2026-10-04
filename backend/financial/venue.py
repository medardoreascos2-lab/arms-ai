"""Provider-neutral venue identities; availability, hours and fees remain unknown."""

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from backend.financial.asset import AssetType


class VenueDataStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    AVAILABLE = "AVAILABLE"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class FinancialVenue:
    venue_id: str
    name: str
    asset_classes: tuple[AssetType, ...]
    timezone: str
    market_hours: str | None = None
    fee_model_reference: str | None = None
    data_status: VenueDataStatus = VenueDataStatus.UNKNOWN

    def __post_init__(self) -> None:
        for name in ("venue_id", "name", "timezone"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonblank")
        if not self.asset_classes or any(not isinstance(kind, AssetType) for kind in self.asset_classes):
            raise ValueError("asset_classes must contain explicit asset types")
        if len(set(self.asset_classes)) != len(self.asset_classes):
            raise ValueError("asset_classes must be unique")
        for name in ("market_hours", "fee_model_reference"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be nonblank when known")
        if not isinstance(self.data_status, VenueDataStatus):
            raise TypeError("data_status must be explicit")


_VENUES = {
    venue.venue_id: venue
    for venue in (
        FinancialVenue("CME", "CME", (AssetType.FUTURE,), "America/Chicago"),
        FinancialVenue("NASDAQ", "NASDAQ", (AssetType.STOCK, AssetType.ETF), "America/New_York"),
        FinancialVenue("NYSE", "NYSE", (AssetType.STOCK, AssetType.ETF), "America/New_York"),
        FinancialVenue("ARCA", "NYSE Arca", (AssetType.ETF,), "America/New_York"),
        FinancialVenue("COINBASE", "Coinbase", (AssetType.CRYPTO_SPOT,), "UTC"),
        FinancialVenue("KRAKEN", "Kraken", (AssetType.CRYPTO_SPOT,), "UTC"),
        FinancialVenue("BINANCE", "Binance", (AssetType.CRYPTO_SPOT,), "UTC"),
    )
}
VENUES = MappingProxyType(_VENUES)


def get_venue(venue_id: str) -> FinancialVenue:
    if not isinstance(venue_id, str) or not venue_id.strip():
        raise ValueError("venue_id must be nonblank")
    try:
        return VENUES[venue_id.strip().upper()]
    except KeyError as exc:
        raise KeyError(f"unknown venue: {venue_id}") from exc
