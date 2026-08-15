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

    service.pipeline.learning_engine.record_result(
        "ATR 2.0 RR 1:3",
        "WIN",
        300,
    )


    service.pipeline.learning_engine.record_result(
        "ATR 2.0 RR 1:3",
        "WIN",
        250,
    )


    service.pipeline.learning_engine.record_result(
        "ATR 2.0 RR 1:3",
        "LOSS",
        -100,
    )


    return service.analyze_strategy(

        strategy="ATR 2.0 RR 1:3",

        backtest_score=47.4,

        market_regime="TRENDING",

        volatility="NORMAL",

    )
