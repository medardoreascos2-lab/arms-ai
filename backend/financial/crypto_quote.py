"""Per-venue crypto quote evidence without exchange execution capability."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from backend.financial.crypto_asset import CryptoAssetIdentity
from backend.financial.market_snapshot import MarketSnapshot
from backend.financial.venue import get_venue


class TransferStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class CryptoVenueQuote:
    asset: CryptoAssetIdentity
    venue_id: str
    snapshot: MarketSnapshot
    bid_depth_base: Decimal | None = None
    ask_depth_base: Decimal | None = None
    buy_fee_rate: Decimal | None = None
    sell_fee_rate: Decimal | None = None
    withdraw_fee_quote: Decimal | None = None
    deposit_status: TransferStatus = TransferStatus.UNKNOWN
    withdraw_status: TransferStatus = TransferStatus.UNKNOWN
    transfer_network: str | None = None
    latency_ms: Decimal | None = None

    def __post_init__(self) -> None:
        get_venue(self.venue_id)
        if self.snapshot.asset_id != self.asset.asset_id:
            raise ValueError("quote asset identity mismatch")
        for name in ("bid_depth_base", "ask_depth_base", "withdraw_fee_quote", "latency_ms"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite() or value < 0
            ):
                raise ValueError(f"{name} must be nonnegative and finite")
        for name in ("buy_fee_rate", "sell_fee_rate"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite() or not 0 <= value < 1
            ):
                raise ValueError(f"{name} must be a finite fraction")
        if not isinstance(self.deposit_status, TransferStatus) or not isinstance(self.withdraw_status, TransferStatus):
            raise TypeError("transfer status must be explicit")
        if self.transfer_network is not None and not self.transfer_network.strip():
            raise ValueError("transfer network must be nonblank when known")
