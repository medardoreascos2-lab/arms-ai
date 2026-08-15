from fastapi import APIRouter


from backend.storage.journal_database import (
    JournalDatabase,
)


from backend.analytics.trade_history_adapter import (
    TradeHistoryAdapter,
)


from backend.learning.ai_pattern_engine import (
    AIPatternEngine,
)



router = APIRouter(

    prefix="/api/v2/dashboard",

    tags=[

        "AI Pattern Intelligence"

    ],

)



adapter = TradeHistoryAdapter()

engine = AIPatternEngine()




@router.get(
    "/ai-pattern"
)
def ai_pattern_dashboard():


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


        "buy_trades":

            report.buy_trades,


        "sell_trades":

            report.sell_trades,


        "average_profit":

            report.average_profit,


        "average_loss":

            report.average_loss,


        "best_direction":

            report.best_direction,


        "pattern_quality":

            report.pattern_quality,


        "insights":

            report.insights,


        "recommendations":

            report.recommendations,


    }
