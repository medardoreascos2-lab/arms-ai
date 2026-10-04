"""Canonical observed trade record for analysis, never order submission."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TradeOrigin(str, Enum):
    PAPER_OBSERVED = "PAPER_OBSERVED"
    ACTUAL_OBSERVED = "ACTUAL_OBSERVED"
    UNKNOWN = "UNKNOWN"


class TradeSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class FinancialTradeRecord:
    record_id: str
    source: str
    origin: TradeOrigin
    asset_id: str
    side: TradeSide
    entry_price: Decimal
    exit_price: Decimal | None
    size: Decimal
    stop_price: Decimal | None
    target_price: Decimal | None
    entry_at: datetime
    exit_at: datetime | None
    strategy: str | None
    market_regime: str | None
    decision_evidence: tuple[str, ...]
    result_pnl: Decimal | None
    fees: Decimal | None
    slippage: Decimal | None

    def __post_init__(self) -> None:
        for name in ("record_id", "source", "asset_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be explicit")
        if not isinstance(self.origin, TradeOrigin) or not isinstance(self.side, TradeSide):
            raise TypeError("trade origin and side must be explicit")
        for name in ("entry_price", "size"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                raise ValueError(f"{name} must be positive and finite")
        for name in ("exit_price", "stop_price", "target_price"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, Decimal) or not value.is_finite() or value <= 0):
                raise ValueError(f"{name} must be positive and finite when known")
        for name in ("result_pnl", "fees", "slippage"):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, Decimal) or not value.is_finite()
                or (name != "result_pnl" and value < 0)
            ):
                raise ValueError(f"{name} must be finite and valid when known")
        if self.entry_at.tzinfo is None or self.entry_at.utcoffset() is None:
            raise ValueError("entry_at must be timezone-aware")
        if self.exit_at is not None and (
            self.exit_at.tzinfo is None or self.exit_at.utcoffset() is None or self.exit_at < self.entry_at
        ):
            raise ValueError("exit_at must be timezone-aware and after entry")
        if self.exit_price is not None and self.exit_at is None:
            raise ValueError("exit price requires exit timestamp")
        if self.result_pnl is not None and self.exit_price is None:
            raise ValueError("result requires observed exit")
        if any(not isinstance(item, str) or not item.strip() for item in self.decision_evidence):
            raise ValueError("decision evidence references must be nonblank")
        object.__setattr__(self, "decision_evidence", tuple(self.decision_evidence))
