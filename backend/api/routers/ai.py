from fastapi import APIRouter

from backend.ai.ai_decision_engine import (
    AIDecisionEngine,
)
from backend.ai.conversation_engine import (
    ConversationEngine,
)
from backend.ai.providers.local_provider import (
    LocalAIProvider,
)
from backend.ai.trading.trading_copilot_service import (
    TradingCopilotService,
)
from backend.api.schemas.ai import (
    AICopilotRequest,
    AIDecisionRequest,
    AITradingContextRequest,
)
from backend.models.candle import Candle
from backend.pipeline.arms_pipeline import (
    ArmsPipeline,
)
from backend.pipeline.backtest_market_stage import (
    BacktestMarketStage,
)
from backend.pipeline.decision_stage import (
    DecisionStage,
)
from backend.pipeline.indicator_stage import (
    IndicatorStage,
)
from backend.pipeline.intelligence_stage import (
    IntelligenceStage,
)
from backend.pipeline.risk_stage import (
    RiskStage,
)
from backend.pipeline.smart_money_stage import (
    SmartMoneyStage,
)


router = APIRouter(
    prefix="/ai",
    tags=["ai"],
)


@router.post("/decision")
def analyze_ai_decision(
    request: AIDecisionRequest,
) -> dict[str, object]:
    return AIDecisionEngine().analyze(
        weights=request.weights,
        metrics=request.metrics,
    )


@router.post("/copilot")
def ask_ai_copilot(
    request: AICopilotRequest,
) -> dict[str, object]:
    return ConversationEngine(
        provider=LocalAIProvider(),
    ).ask(
        question=request.question,
        weights=request.weights,
        metrics=request.metrics,
    )


@router.post("/trading-context")
def analyze_trading_context(
    request: AITradingContextRequest,
) -> dict[str, object]:
    candles = [
        Candle(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
            timestamp=candle.timestamp,
        )
        for candle in request.candles
    ]

    pipeline = ArmsPipeline(
        stages=[
            BacktestMarketStage(
                max_candles=max(
                    500,
                    len(candles),
                ),
            ),
            IndicatorStage(),
            SmartMoneyStage(),
            IntelligenceStage(),
            RiskStage(
                account_balance=(
                    request.account_balance
                ),
                risk_percent=(
                    request.risk_percent
                ),
                reward_risk_ratio=(
                    request.reward_risk_ratio
                ),
                point_value=(
                    request.point_value
                ),
            ),
            DecisionStage(
                reward_risk_ratio=(
                    request.reward_risk_ratio
                ),
            ),
        ]
    )

    pipeline_context = pipeline.run(
        initial_context={
            "symbol": request.symbol,
            "timeframe": request.timeframe,
            "backtest_candles": candles,
        }
    )

    return TradingCopilotService().build_context(
        pipeline_context
    )
