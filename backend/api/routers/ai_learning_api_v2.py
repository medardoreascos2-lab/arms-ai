from fastapi import APIRouter


from backend.storage.journal_database import (
    JournalDatabase,
)


from backend.analytics.trade_history_adapter import (
    TradeHistoryAdapter,
)


from backend.learning.ai_learning_engine import (
    AILearningEngine,
)



router = APIRouter(

    prefix="/api/v2/dashboard",

    tags=[

        "AI Learning Intelligence"

    ],

)



adapter = TradeHistoryAdapter()

engine = AILearningEngine()




@router.get(
    "/ai-learning"
)
def ai_learning_dashboard():


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


        "win_rate":

            report.win_rate,


        "total_profit":

            report.total_profit,


        "performance_level":

            report.performance_level,


        "insights":

            report.insights,


        "recommendations":

            report.recommendations,


    }
