"""Shadow MEDAR decision paired with an observed user/PAPER trade."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from backend.financial.trade_record import FinancialTradeRecord, TradeSide


@dataclass(frozen=True)
class ShadowDecision:
    trade_record_id: str
    asset_id: str
    decided_at: datetime
    would_trade: bool | None
    side: TradeSide | None
    entry: Decimal | None
    stop: Decimal | None
    target: Decimal | None
    reason: str
    confidence: Decimal | None
    evidence: tuple[str, ...]
    label: str = "HYPOTHETICAL"
    execution_authority: bool = False

    def __post_init__(self) -> None:
        if not self.trade_record_id.strip() or not self.asset_id.strip() or not self.reason.strip():
            raise ValueError("shadow decision identity and reason are required")
        if self.decided_at.tzinfo is None or self.decided_at.utcoffset() is None:
            raise ValueError("decision time must be timezone-aware")
        if self.would_trade is not None and type(self.would_trade) is not bool:
            raise TypeError("would_trade must be boolean or unknown")
        if self.would_trade is True:
            if not isinstance(self.side, TradeSide):
                raise ValueError("shadow trade requires explicit side")
            for name in ("entry", "stop", "target"):
                value = getattr(self, name)
                if not isinstance(value, Decimal) or not value.is_finite() or value <= 0:
                    raise ValueError("shadow trade requires positive finite plan prices")
            if not ((self.side is TradeSide.LONG and self.stop < self.entry < self.target)
                    or (self.side is TradeSide.SHORT and self.target < self.entry < self.stop)):
                raise ValueError("shadow stop and target must bracket entry")
            if self.confidence is None or not isinstance(self.confidence, Decimal) or not self.confidence.is_finite() or not 0 <= self.confidence <= 1:
                raise ValueError("shadow trade requires bounded confidence")
            if not self.evidence:
                raise ValueError("shadow trade requires decision-time evidence")
        elif self.side is not None or any(getattr(self, name) is not None for name in ("entry", "stop", "target")):
            raise ValueError("non-trade shadow decision cannot carry a trade plan")
        if any(not isinstance(item, str) or not item.strip() for item in self.evidence):
            raise ValueError("shadow evidence references must be nonblank")
        if self.execution_authority or self.label != "HYPOTHETICAL":
            raise ValueError("shadow decisions cannot authorize execution")
        object.__setattr__(self, "evidence", tuple(self.evidence))


@dataclass(frozen=True)
class ShadowDecisionPair:
    user_decision: FinancialTradeRecord
    medar_shadow_decision: ShadowDecision

    def __post_init__(self) -> None:
        if (
            self.user_decision.record_id != self.medar_shadow_decision.trade_record_id
            or self.user_decision.asset_id != self.medar_shadow_decision.asset_id
        ):
            raise ValueError("shadow decision must match observed trade")
        if self.medar_shadow_decision.decided_at > self.user_decision.entry_at:
            raise ValueError("shadow decision must precede observed entry")
