from dataclasses import dataclass

from fastapi import APIRouter, Request

from backend.learning.ai_learning_engine import (
    AILearningEngine,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=["AI Learning"],
)


@dataclass
class CanonicalLearningTrade:
    profit: float


@router.get("/ai-learning")
def get_ai_learning(
    request: Request,
):
    journal = request.app.state.trade_journal_v2

    canonical_trades = journal.get_closed_trades()

    trades = [
        CanonicalLearningTrade(
            profit=float(trade.pnl),
        )
        for trade in canonical_trades
    ]

    engine = AILearningEngine()

    report = engine.analyze(trades)

    return {
        "trades_analyzed": report.trades_analyzed,
        "win_rate": report.win_rate,
        "total_profit": report.total_profit,
        "performance_level": report.performance_level,
        "insights": report.insights,
        "recommendations": report.recommendations,
    }
