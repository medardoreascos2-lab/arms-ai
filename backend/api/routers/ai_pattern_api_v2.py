from dataclasses import dataclass

from fastapi import APIRouter, Request

from backend.learning.ai_pattern_engine import AIPatternEngine


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=["AI Pattern"],
)


@dataclass
class CanonicalPatternTrade:
    direction: str
    profit: float


def _legacy_direction(direction: str) -> str:
    normalized = str(direction).upper()

    if normalized == "LONG":
        return "BUY"

    if normalized == "SHORT":
        return "SELL"

    return normalized


@router.get("/ai-pattern")
def get_ai_pattern(request: Request):
    journal = request.app.state.trade_journal_v2
    canonical_trades = journal.get_closed_trades()

    trades = [
        CanonicalPatternTrade(
            direction=_legacy_direction(trade.direction),
            profit=float(trade.pnl),
        )
        for trade in canonical_trades
    ]

    engine = AIPatternEngine()
    report = engine.analyze(trades)

    return {
        "trades_analyzed": report.trades_analyzed,
        "buy_trades": report.buy_trades,
        "sell_trades": report.sell_trades,
        "average_profit": report.average_profit,
        "average_loss": report.average_loss,
        "best_direction": report.best_direction,
        "pattern_quality": report.pattern_quality,
        "insights": report.insights,
        "recommendations": report.recommendations,
    }
