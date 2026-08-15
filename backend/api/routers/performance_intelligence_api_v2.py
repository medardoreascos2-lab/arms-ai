from fastapi import APIRouter

from backend.analytics.trade_performance_engine import (
    TradePerformanceEngine,
)

from backend.analytics.trade_history_adapter import (
    TradeHistoryAdapter,
)

from backend.storage.journal_database import (
    JournalDatabase,
)



router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Performance Intelligence"
    ],
)



performance_engine = TradePerformanceEngine()

adapter = TradeHistoryAdapter()




@router.get(
    "/performance-intelligence"
)
def performance_intelligence_dashboard():


    database = JournalDatabase()

    database_trades = database.get_trades()


    trades = adapter.convert_database_trades(
        database_trades
    )


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
