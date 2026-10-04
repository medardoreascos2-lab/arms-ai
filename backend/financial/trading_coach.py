"""Trading coach summaries derived only from observed, same-origin trade cohorts."""

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal

from backend.financial.trade_behavior import BehaviorReview, BehaviorTag
from backend.financial.trade_record import FinancialTradeRecord, TradeOrigin


@dataclass(frozen=True)
class TradingCoachSummary:
    asset_id: str
    origin: TradeOrigin
    sample_size: int
    observed_result_count: int
    what_worked: str | None
    what_failed: str | None
    top_mistake: BehaviorTag | None
    best_setup: str | None
    worst_regime: str | None
    risk_discipline: str
    actionable_improvement: str | None
    analysis_only: bool = True


def summarize_trades(
    trades: tuple[FinancialTradeRecord, ...],
    reviews: tuple[BehaviorReview, ...],
) -> TradingCoachSummary:
    if not trades:
        raise ValueError("coach summary requires observed trades")
    if len({t.asset_id for t in trades}) != 1 or len({t.origin for t in trades}) != 1:
        raise ValueError("coach cohort must keep instrument and origin separate")
    if len({t.record_id for t in trades}) != len(trades) or len(reviews) != len(trades):
        raise ValueError("one review per unique trade is required")
    strategy_results: dict[str, list[Decimal]] = defaultdict(list)
    regime_results: dict[str, list[Decimal]] = defaultdict(list)
    findings = Counter()
    known_risk_checks = 0
    for trade, review in zip(trades, reviews):
        if any(finding.trade_id != trade.record_id for finding in review.findings):
            raise ValueError("review trade identity mismatch")
        if trade.result_pnl is not None:
            if trade.strategy:
                strategy_results[trade.strategy].append(trade.result_pnl)
            if trade.market_regime:
                regime_results[trade.market_regime].append(trade.result_pnl)
        findings.update(finding.tag for finding in review.findings)
        if BehaviorTag.RISK_INCONSISTENCY not in review.unknown_checks:
            known_risk_checks += 1
    ranked_strategies = sorted(
        strategy_results,
        key=lambda name: (sum(strategy_results[name]) / len(strategy_results[name]), name),
    )
    ranked_regimes = sorted(
        regime_results,
        key=lambda name: (sum(regime_results[name]) / len(regime_results[name]), name),
    )
    best = ranked_strategies[-1] if ranked_strategies and sum(strategy_results[ranked_strategies[-1]]) > 0 else None
    worst = ranked_strategies[0] if ranked_strategies and sum(strategy_results[ranked_strategies[0]]) < 0 else None
    top_mistake = findings.most_common(1)[0][0] if findings else None
    if findings[BehaviorTag.RISK_INCONSISTENCY]:
        discipline = "RISK_BREACH_OBSERVED"
    elif known_risk_checks == len(trades):
        discipline = "NO_RISK_BREACH_IN_REVIEWED_TRADES"
    else:
        discipline = "UNKNOWN"
    return TradingCoachSummary(
        trades[0].asset_id, trades[0].origin, len(trades),
        sum(t.result_pnl is not None for t in trades),
        best,
        worst,
        top_mistake,
        best,
        ranked_regimes[0] if ranked_regimes else None,
        discipline,
        f"Review {top_mistake.value} against supplied trade plans" if top_mistake else None,
    )
