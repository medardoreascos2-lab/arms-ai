"""Evidence-bounded trade behavior findings; no psychological diagnosis."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from backend.financial.trade_record import FinancialTradeRecord, TradeSide


class BehaviorTag(str, Enum):
    EARLY_ENTRY = "EARLY_ENTRY"
    LATE_ENTRY = "LATE_ENTRY"
    OVERTRADING = "OVERTRADING"
    REVENGE_PATTERN_PROXY = "REVENGE_PATTERN_PROXY"
    RISK_INCONSISTENCY = "RISK_INCONSISTENCY"
    STOP_WIDENING = "STOP_WIDENING"
    STRATEGY_DEVIATION = "STRATEGY_DEVIATION"
    SESSION_RULE_VIOLATION = "SESSION_RULE_VIOLATION"


@dataclass(frozen=True)
class TradeBehaviorEvidence:
    planned_entry_start: datetime | None = None
    planned_entry_end: datetime | None = None
    session_trade_index: int | None = None
    max_session_trades: int | None = None
    prior_loss_exit_at: datetime | None = None
    minimum_cooldown: timedelta | None = None
    point_value: Decimal | None = None
    max_risk_quote: Decimal | None = None
    original_stop: Decimal | None = None
    approved_strategy: str | None = None
    session_rule_violation_reference: str | None = None


@dataclass(frozen=True)
class BehaviorFinding:
    tag: BehaviorTag
    evidence: str
    trade_id: str


@dataclass(frozen=True)
class BehaviorReview:
    findings: tuple[BehaviorFinding, ...]
    unknown_checks: tuple[BehaviorTag, ...]
    analysis_only: bool = True


def analyze_trade_behavior(trade: FinancialTradeRecord, evidence: TradeBehaviorEvidence) -> BehaviorReview:
    findings = []
    unknown = []

    def add(tag: BehaviorTag, explanation: str) -> None:
        findings.append(BehaviorFinding(tag, explanation, trade.record_id))

    if evidence.planned_entry_start is None or evidence.planned_entry_end is None:
        unknown.extend((BehaviorTag.EARLY_ENTRY, BehaviorTag.LATE_ENTRY))
    else:
        if evidence.planned_entry_start.tzinfo is None or evidence.planned_entry_end.tzinfo is None or evidence.planned_entry_start > evidence.planned_entry_end:
            raise ValueError("planned entry window must be valid and timezone-aware")
        if trade.entry_at < evidence.planned_entry_start:
            add(BehaviorTag.EARLY_ENTRY, "entry precedes supplied planned window")
        elif trade.entry_at > evidence.planned_entry_end:
            add(BehaviorTag.LATE_ENTRY, "entry follows supplied planned window")

    if evidence.session_trade_index is None or evidence.max_session_trades is None:
        unknown.append(BehaviorTag.OVERTRADING)
    elif evidence.session_trade_index <= 0 or evidence.max_session_trades <= 0:
        raise ValueError("session trade limits must be positive")
    elif evidence.session_trade_index > evidence.max_session_trades:
        add(BehaviorTag.OVERTRADING, "supplied session trade limit exceeded")

    if evidence.prior_loss_exit_at is None or evidence.minimum_cooldown is None:
        unknown.append(BehaviorTag.REVENGE_PATTERN_PROXY)
    else:
        if evidence.prior_loss_exit_at.tzinfo is None or evidence.minimum_cooldown < timedelta(0):
            raise ValueError("prior loss time and cooldown must be valid")
        interval = trade.entry_at - evidence.prior_loss_exit_at
        if timedelta(0) <= interval < evidence.minimum_cooldown:
            add(BehaviorTag.REVENGE_PATTERN_PROXY, "entry occurred inside supplied post-loss cooldown")

    if trade.stop_price is None or evidence.point_value is None or evidence.max_risk_quote is None:
        unknown.append(BehaviorTag.RISK_INCONSISTENCY)
    else:
        if evidence.point_value <= 0 or evidence.max_risk_quote <= 0:
            raise ValueError("point value and max risk must be positive")
        observed_risk = abs(trade.entry_price - trade.stop_price) * trade.size * evidence.point_value
        if observed_risk > evidence.max_risk_quote:
            add(BehaviorTag.RISK_INCONSISTENCY, "observed stop distance exceeds supplied risk cap")

    if evidence.original_stop is None or trade.stop_price is None:
        unknown.append(BehaviorTag.STOP_WIDENING)
    elif (trade.side is TradeSide.LONG and trade.stop_price < evidence.original_stop) or (
        trade.side is TradeSide.SHORT and trade.stop_price > evidence.original_stop
    ):
        add(BehaviorTag.STOP_WIDENING, "observed stop moved farther from entry")

    if evidence.approved_strategy is None or trade.strategy is None:
        unknown.append(BehaviorTag.STRATEGY_DEVIATION)
    elif trade.strategy != evidence.approved_strategy:
        add(BehaviorTag.STRATEGY_DEVIATION, "observed strategy differs from supplied plan")

    if evidence.session_rule_violation_reference is None:
        unknown.append(BehaviorTag.SESSION_RULE_VIOLATION)
    else:
        add(BehaviorTag.SESSION_RULE_VIOLATION, evidence.session_rule_violation_reference)

    return BehaviorReview(tuple(findings), tuple(unknown))
