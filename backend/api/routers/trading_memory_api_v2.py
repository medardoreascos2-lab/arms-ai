from fastapi import APIRouter


from backend.storage.journal_database import (
    JournalDatabase,
)


from backend.analytics.trade_history_adapter import (
    TradeHistoryAdapter,
)


from backend.learning.trading_memory_engine import (
    TradingMemoryEngine,
)



router = APIRouter(

    prefix="/api/v2/dashboard",

    tags=[

        "AI Trading Memory Intelligence"

    ],

)



adapter = TradeHistoryAdapter()

engine = TradingMemoryEngine()



@router.get(
    "/trading-memory"
)
def trading_memory_dashboard():


    database = JournalDatabase()


    database_trades = database.get_trades()


    trades = adapter.convert_database_trades(
        database_trades
    )


    report = engine.analyze(
        trades
    )


    return {


        "trades_analyzed":

            report.trades_analyzed,


        "buy_count":

            report.buy_count,


        "sell_count":

            report.sell_count,


        "dominant_strategy":

            report.dominant_strategy,


        "memory_quality":

            report.memory_quality,


        "winning_patterns":

            report.winning_patterns,


        "losing_patterns":

            report.losing_patterns,


        "insights":

            report.insights,


        "recommendations":

            report.recommendations,


    }
