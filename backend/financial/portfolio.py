"""Read-only portfolio holdings and valuation from supplied observations."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Mapping

from backend.financial.asset import AssetType


def _finite(value: Decimal, name: str, *, positive: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite() or (value <= 0 if positive else value < 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")


@dataclass(frozen=True)
class PortfolioPosition:
    asset_id: str
    asset_type: AssetType
    currency: str
    quantity: Decimal
    cost_basis_total: Decimal
    current_price: Decimal | None = None
    realized_pnl: Decimal | None = None
    sector: str | None = None

    def __post_init__(self) -> None:
        if not self.asset_id.strip() or not self.currency.strip() or not isinstance(self.asset_type, AssetType):
            raise ValueError("position identity, type and currency are required")
        _finite(self.quantity, "quantity", positive=True)
        _finite(self.cost_basis_total, "cost_basis_total")
        if self.current_price is not None:
            _finite(self.current_price, "current_price")
        if self.realized_pnl is not None and (
            not isinstance(self.realized_pnl, Decimal) or not self.realized_pnl.is_finite()
        ):
            raise ValueError("realized_pnl must be finite when known")

    @property
    def current_value(self) -> Decimal | None:
        return self.quantity * self.current_price if self.current_price is not None else None

    @property
    def unrealized_pnl(self) -> Decimal | None:
        value = self.current_value
        return value - self.cost_basis_total if value is not None else None


@dataclass(frozen=True)
class PortfolioSnapshot:
    portfolio_id: str
    currency: str
    source: str
    observed_at: datetime
    positions: tuple[PortfolioPosition, ...] = ()
    cash: Mapping[str, Decimal] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.portfolio_id.strip() or not self.currency.strip() or not self.source.strip():
            raise ValueError("portfolio identity, currency and source are required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if len({p.asset_id for p in self.positions}) != len(self.positions):
            raise ValueError("duplicate portfolio position")
        if any(p.currency != self.currency for p in self.positions):
            raise ValueError("cross-currency valuation requires explicit FX conversion")
        if any(k != self.currency for k in self.cash):
            raise ValueError("cross-currency cash requires explicit FX conversion")
        for value in self.cash.values():
            _finite(value, "cash")
        object.__setattr__(self, "positions", tuple(self.positions))
        object.__setattr__(self, "cash", MappingProxyType(dict(self.cash)))

    @property
    def current_value(self) -> Decimal | None:
        values = [p.current_value for p in self.positions]
        if any(value is None for value in values):
            return None
        return sum(values, sum(self.cash.values(), Decimal(0)))

    @property
    def unrealized_pnl(self) -> Decimal | None:
        values = [p.unrealized_pnl for p in self.positions]
        return None if any(value is None for value in values) else sum(values, Decimal(0))

    @property
    def realized_pnl(self) -> Decimal | None:
        values = [p.realized_pnl for p in self.positions]
        return None if any(value is None for value in values) else sum(values, Decimal(0))

    def allocation(self) -> Mapping[str, Decimal] | None:
        total = self.current_value
        if total is None or total <= 0:
            return None
        return MappingProxyType({p.asset_id: p.current_value / total for p in self.positions})
