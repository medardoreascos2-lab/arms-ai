"""NQ/MNQ Trading Coach integration over same-instrument observed cohorts."""

from dataclasses import dataclass

from backend.financial.futures_regime import RegimePerformance, analyze_regime_performance
from backend.financial.futures_session import FuturesTradeContext, SessionAnalytics, analyze_futures_sessions
from backend.financial.futures_setup import SetupPerformance, analyze_setup_performance
from backend.financial.trade_behavior import BehaviorReview
from backend.financial.trading_coach import TradingCoachSummary, summarize_trades


@dataclass(frozen=True)
class FuturesCoachReport:
    coach: TradingCoachSummary
    sessions: SessionAnalytics
    setups: SetupPerformance
    regimes: RegimePerformance
    priority_note: str | None
    analysis_only: bool = True


def build_futures_coach_report(
    contexts: tuple[FuturesTradeContext, ...],
    reviews: tuple[BehaviorReview, ...],
) -> FuturesCoachReport:
    sessions = analyze_futures_sessions(contexts)
    setups = analyze_setup_performance(contexts)
    regimes = analyze_regime_performance(contexts)
    coach = summarize_trades(tuple(context.trade for context in contexts), reviews)
    negative_setups = [
        (tag, stats) for tag, stats in setups.groups.items()
        if stats.expectancy_quote is not None and stats.expectancy_quote < 0
    ]
    worst = min(negative_setups, key=lambda pair: pair[1].expectancy_quote) if negative_setups else None
    note = (
        f"Review observed {worst[0].value} losses in {sessions.root.value}; "
        f"sample={worst[1].observed_result_count}"
        if worst else None
    )
    return FuturesCoachReport(coach, sessions, setups, regimes, note)
