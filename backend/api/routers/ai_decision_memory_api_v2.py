from dataclasses import dataclass

from fastapi import APIRouter, Request

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


memory_engine = MemoryScoringEngine()
decision_adapter = DecisionMemoryAdapter()


@dataclass
class CanonicalMemoryTrade:
    profit: float


@router.get(
    "/ai-decision-memory"
)
def ai_decision_memory_dashboard(
    request: Request,
):

    journal = (
        request.app.state.trade_journal_v2
    )

    closed_trades = (
        journal.get_closed_trades()
    )

    trades = [
        CanonicalMemoryTrade(
            profit=float(trade.pnl),
        )
        for trade in closed_trades
    ]

    memory_report = (
        memory_engine.calculate(
            trades
        )
    )

    decision_report = (
        decision_adapter.evaluate(
            technical_confidence=93,
            memory_report=memory_report,
        )
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
                "memory_adjustment",
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
