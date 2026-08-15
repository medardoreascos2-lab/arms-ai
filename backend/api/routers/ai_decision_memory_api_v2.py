from fastapi import APIRouter


from backend.storage.journal_database import (
    JournalDatabase,
)


from backend.analytics.trade_history_adapter import (
    TradeHistoryAdapter,
)


from backend.learning.memory_scoring_engine import (
    MemoryScoringEngine,
)


from backend.intelligence.decision_memory_adapter import (
    DecisionMemoryAdapter,
)



router = APIRouter(

    prefix="/api/v2/dashboard",

    tags=[

        "AI Decision Memory Intelligence"

    ],

)



adapter = TradeHistoryAdapter()

memory_engine = MemoryScoringEngine()

decision_adapter = DecisionMemoryAdapter()



@router.get(
    "/ai-decision-memory"
)
def ai_decision_memory_dashboard():


    database = JournalDatabase()


    database_trades = database.get_trades()


    trades = adapter.convert_database_trades(
        database_trades
    )


    memory_report = memory_engine.calculate(
        trades
    )


    decision_report = decision_adapter.evaluate(

        technical_confidence=93,

        memory_report=memory_report

    )


    return {


        "technical_confidence":

            decision_report.technical_confidence,


        "memory_confidence":

            decision_report.memory_confidence,


        "memory_adjustment":

            decision_report.memory_adjustment
            if hasattr(
                decision_report,
                "memory_adjustment"
            )
            else memory_report.adjustment,


        "final_confidence":

            decision_report.final_confidence,


        "memory_reliability":

            decision_report.memory_reliability,


        "decision":

            decision_report.decision,


        "explanation":

            decision_report.explanation,


        "recommendations":

            decision_report.recommendations,


    }
