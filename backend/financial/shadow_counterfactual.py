"""Historical-path shadow counterfactuals with conservative intrabar ambiguity."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum

from backend.financial.shadow_decision import ShadowDecision
from backend.financial.trade_record import TradeSide


class CounterfactualStatus(str, Enum):
    RESOLVED = "RESOLVED"
    NO_ENTRY_IN_PATH = "NO_ENTRY_IN_PATH"
    UNRESOLVED = "UNRESOLVED"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"


@dataclass(frozen=True)
class HistoricalPriceBar:
    start_at: datetime
    end_at: datetime
    low: Decimal
    high: Decimal
    source: str

    def __post_init__(self) -> None:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None or self.end_at <= self.start_at:
            raise ValueError("bar times must be aware and ordered")
        if not isinstance(self.low, Decimal) or not isinstance(self.high, Decimal) or not self.low.is_finite() or not self.high.is_finite() or self.low <= 0 or self.high < self.low:
            raise ValueError("bar prices must be positive and ordered")
        if not self.source.strip():
            raise ValueError("bar source is required")


@dataclass(frozen=True)
class CounterfactualResult:
    trade_record_id: str
    status: CounterfactualStatus
    entry_at: datetime | None
    exit_at: datetime | None
    exit_price: Decimal | None
    net_pnl_quote: Decimal | None
    dataset_reference: str
    assumptions: tuple[str, ...]
    labels: tuple[str, str, str] = ("HYPOTHETICAL", "COUNTERFACTUAL", "NOT_EXECUTED")
    execution_authority: bool = False


def compute_counterfactual(
    decision: ShadowDecision,
    bars: tuple[HistoricalPriceBar, ...],
    dataset_reference: str,
    size: Decimal,
    point_value: Decimal,
    fees_quote: Decimal,
    slippage_quote: Decimal,
) -> CounterfactualResult:
    if not dataset_reference.strip():
        raise ValueError("historical dataset reference is required")
    for name, value, positive in (
        ("size", size, True), ("point_value", point_value, True),
        ("fees_quote", fees_quote, False), ("slippage_quote", slippage_quote, False),
    ):
        if not isinstance(value, Decimal) or not value.is_finite() or (value <= 0 if positive else value < 0):
            raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    if decision.would_trade is None:
        return CounterfactualResult(decision.trade_record_id, CounterfactualStatus.INCOMPLETE_DATA,
                                    None, None, None, None, dataset_reference, ("SHADOW_DECISION_UNKNOWN",))
    if decision.would_trade is False:
        return CounterfactualResult(decision.trade_record_id, CounterfactualStatus.NO_ENTRY_IN_PATH,
                                    None, None, None, Decimal(0), dataset_reference, ("SHADOW_DECLINED_TRADE",))
    if not bars:
        return CounterfactualResult(decision.trade_record_id, CounterfactualStatus.INCOMPLETE_DATA,
                                    None, None, None, None, dataset_reference, ("NO_HISTORICAL_PATH",))
    prior_end = decision.decided_at
    for bar in bars:
        if bar.start_at < prior_end:
            raise ValueError("historical path overlaps decision time or prior bar")
        prior_end = bar.end_at
    entered_at = None
    assumptions = []
    for bar in bars:
        if entered_at is None:
            if not bar.low <= decision.entry <= bar.high:
                continue
            entered_at = bar.start_at
        gap_through_exit = (
            (decision.side is TradeSide.LONG and (bar.high < decision.stop or bar.low > decision.target))
            or (decision.side is TradeSide.SHORT and (bar.low > decision.stop or bar.high < decision.target))
        )
        if gap_through_exit:
            return CounterfactualResult(
                decision.trade_record_id, CounterfactualStatus.INCOMPLETE_DATA,
                entered_at, None, None, None, dataset_reference,
                ("GAP_THROUGH_EXIT_FILL_UNKNOWN",),
            )
        stop_hit = bar.low <= decision.stop <= bar.high
        target_hit = bar.low <= decision.target <= bar.high
        if stop_hit or target_hit:
            if stop_hit and target_hit:
                assumptions.append("STOP_FIRST_ON_AMBIGUOUS_BAR")
            exit_price = decision.stop if stop_hit else decision.target
            direction = Decimal(1) if decision.side is TradeSide.LONG else Decimal(-1)
            pnl = (exit_price - decision.entry) * direction * size * point_value - fees_quote - slippage_quote
            return CounterfactualResult(decision.trade_record_id, CounterfactualStatus.RESOLVED,
                                        entered_at, bar.end_at, exit_price, pnl,
                                        dataset_reference, tuple(assumptions))
    if entered_at is None:
        return CounterfactualResult(decision.trade_record_id, CounterfactualStatus.NO_ENTRY_IN_PATH,
                                    None, None, None, Decimal(0), dataset_reference, ("NO_ENTRY_IN_SUPPLIED_PATH",))
    return CounterfactualResult(decision.trade_record_id, CounterfactualStatus.UNRESOLVED,
                                entered_at, None, None, None, dataset_reference, ("PATH_ENDED_WITH_OPEN_HYPOTHETICAL",))
