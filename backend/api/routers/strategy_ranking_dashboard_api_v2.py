from fastapi import APIRouter

from backend.backtesting.strategy_intelligence_orchestrator_v1 import (
    StrategyIntelligenceOrchestratorV1,
)

from backend.dashboard.strategy_intelligence_dashboard_provider_v1 import (
    StrategyIntelligenceDashboardProviderV1,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=[
        "Strategy Ranking Dashboard"
    ],
)


@router.get(
    "/strategy-ranking"
)
def strategy_ranking_dashboard():

    orchestrator = (
        StrategyIntelligenceOrchestratorV1()
    )


    provider = (
        StrategyIntelligenceDashboardProviderV1(
            intelligence_orchestrator=orchestrator
        )
    )


    strategies = [
        {
            "name": "ATR 1.5 RR 1:2",
            "score": 41.6,
        },
        {
            "name": "ATR 2.0 RR 1:3",
            "score": 47.4,
        },
        {
            "name": "ATR 2.5 RR 1:2",
            "score": 44.8,
        },
    ]


    return (
        provider.get_strategy_intelligence(
            strategies
        )
    )
