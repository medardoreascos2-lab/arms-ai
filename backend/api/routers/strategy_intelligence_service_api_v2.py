from fastapi import APIRouter

from backend.intelligence.strategy_intelligence_service_v1 import (
    StrategyIntelligenceServiceV1,
)


router = APIRouter(
    prefix="/api/v2/strategy",
    tags=[
        "Strategy Intelligence Service"
    ],
)


service = StrategyIntelligenceServiceV1()



@router.get(
    "/intelligence"
)
def get_strategy_intelligence():
    """Observe availability without executing or repairing strategic analysis.

    The current stores have no source IDs, dataset references or calculation
    linkage. Their contents can include results fabricated by the former GET,
    so presence alone cannot establish provenance. No verified precomputed
    intelligence source is currently connected to this service.
    """
    pipeline = service.pipeline
    has_records = any((
        pipeline.learning_engine.history,
        pipeline.adaptive_engine.decisions,
        pipeline.market_engine.analysis,
        pipeline.autonomous_engine.decisions,
        pipeline.memory_engine.memory,
    ))
    data_status = "UNVERIFIABLE_PROVENANCE" if has_records else "NO_DATA"

    # Unknown metrics stay null: zero would imply a verified measurement.
    return {
        "status": "UNAVAILABLE",
        "data_status": data_status,
        "source": None,
        "strategy": None,
        "final_decision": "UNAVAILABLE",
        "confidence": None,
        "reason": [data_status],
        "scores": {"backtest": None, "learning": None, "final": None},
        "market": {"regime": None, "volatility": None, "compatibility": None},
        "history": {"trades": None, "win_rate": None},
    }
