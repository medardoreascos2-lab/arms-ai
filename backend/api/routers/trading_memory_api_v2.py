from dataclasses import dataclass

from fastapi import APIRouter, Request

from backend.learning.trading_memory_engine import TradingMemoryEngine


router = APIRouter()

memory_engine = TradingMemoryEngine()


@dataclass
class CanonicalMemoryTrade:
    direction: str
    profit: float
    strategy: str


def _legacy_direction(direction: str) -> str:
    normalized = str(direction).upper()

    if normalized == "LONG":
        return "BUY"

    if normalized == "SHORT":
        return "SELL"

    return normalized


@router.get("/api/v2/dashboard/trading-memory")
def get_trading_memory(request: Request):

    journal = request.app.state.trade_journal_v2

    canonical_trades = journal.get_closed_trades()

    trades = [
        CanonicalMemoryTrade(
            direction=_legacy_direction(trade.direction),
            profit=float(trade.pnl),
            strategy="UNKNOWN",
        )
        for trade in canonical_trades
    ]

    report = memory_engine.analyze(trades)

    return {
        "trades_analyzed": report.trades_analyzed,
        "buy_count": report.buy_count,
        "sell_count": report.sell_count,
        "dominant_strategy": report.dominant_strategy,
        "memory_quality": report.memory_quality,
        "winning_patterns": report.winning_patterns,
        "losing_patterns": report.losing_patterns,
        "insights": report.insights,
        "recommendations": report.recommendations,
    }
