from dataclasses import dataclass

from fastapi import APIRouter, Request

from backend.analytics.trade_performance_engine import (
    TradePerformanceEngine,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Performance Intelligence"
    ],
)


performance_engine = TradePerformanceEngine()


@dataclass
class CanonicalPerformanceTrade:
    profit: float
    direction: str
    symbol: str
    strategy: str


@router.get(
    "/performance-intelligence"
)
def performance_intelligence_dashboard(
    request: Request,
):

    journal = (
        request.app.state.trade_journal_v2
    )

    closed_trades = (
        journal.get_closed_trades()
    )

    trades = [
        CanonicalPerformanceTrade(
            profit=float(
                trade.pnl
            ),
            direction=str(
                trade.direction
            ),
            symbol=str(
                trade.symbol
            ),
            strategy="UNKNOWN",
        )
        for trade in closed_trades
    ]

    report = performance_engine.analyze(
        trades
    )

    return {
        "total_trades":
            report.total_trades,

        "winning_trades":
            report.winning_trades,

        "losing_trades":
            report.losing_trades,

        "win_rate":
            report.win_rate,

        "total_profit":
            report.total_profit,

        "average_trade":
            report.average_trade,

        "best_trade":
            report.best_trade,

        "worst_trade":
            report.worst_trade,
    }
