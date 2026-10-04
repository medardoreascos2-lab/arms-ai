"""Canonical, analysis-only asset identity and contract metadata."""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class AssetType(str, Enum):
    FUTURE = "FUTURE"
    STOCK = "STOCK"
    ETF = "ETF"
    CRYPTO_SPOT = "CRYPTO_SPOT"
    CRYPTO_PERPETUAL = "CRYPTO_PERPETUAL"
    FOREX = "FOREX"
    INDEX = "INDEX"
    CASH = "CASH"
    STABLECOIN = "STABLECOIN"


def _positive_decimal(value: Decimal | None, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
        raise ValueError(f"{name} must be a positive finite Decimal when known")


@dataclass(frozen=True)
class FinancialAsset:
    """Identity never grants trading authority; missing specifications stay unknown."""

    asset_id: str
    symbol: str
    venue: str | None
    currency: str
    asset_type: AssetType
    contract_multiplier: Decimal | None = None
    tick_size: Decimal | None = None
    point_value: Decimal | None = None
    trading_hours: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("asset_id", "symbol", "currency"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be nonblank and canonical")
        if not isinstance(self.asset_type, AssetType):
            raise TypeError("asset_type must be an AssetType")
        if self.venue is not None and (not isinstance(self.venue, str) or not self.venue.strip()):
            raise ValueError("venue must be nonblank when known")
        if self.trading_hours is not None and (not isinstance(self.trading_hours, str) or not self.trading_hours.strip()):
            raise ValueError("trading_hours must be nonblank when known")
        for name in ("contract_multiplier", "tick_size", "point_value"):
            _positive_decimal(getattr(self, name), name)
        if self.asset_type in (AssetType.FUTURE, AssetType.CRYPTO_PERPETUAL):
            if self.venue is None or self.contract_multiplier is None or self.tick_size is None or self.point_value is None:
                raise ValueError("derivative identity requires venue and explicit contract specifications")
        if not isinstance(self.metadata, Mapping) or any(
            not isinstance(k, str) or not k.strip() or not isinstance(v, str)
            for k, v in self.metadata.items()
        ):
            raise ValueError("metadata must contain string keys and values")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
