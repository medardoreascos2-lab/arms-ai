from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    status,
)

from backend.ai.trading.trading_copilot_service import (
    TradingCopilotService,
)
from backend.api.schemas.market import (
    LiveMarketAnalysisRequest,
    MarketWebhookRequest,
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
from backend.services.live_candle_store import (
    LiveCandleStore,
)


router = APIRouter(
    prefix="/market",
    tags=["market"],
)


def get_live_store(
    request: Request,
) -> LiveCandleStore:
    store = request.app.state.live_candle_store

    if not isinstance(
        store,
        LiveCandleStore,
    ):
        raise RuntimeError(
            "LiveCandleStore no está configurado."
        )

    return store


@router.post(
    "/webhook",
    status_code=status.HTTP_201_CREATED,
)
def receive_market_webhook(
    payload: MarketWebhookRequest,
    request: Request,
) -> dict[str, object]:
    store = get_live_store(
        request
    )

    candle = Candle(
        symbol=payload.symbol.strip(),
        timeframe=payload.timeframe.strip(),
        open=payload.open,
        high=payload.high,
        low=payload.low,
        close=payload.close,
        volume=payload.volume,
        timestamp=payload.timestamp,
    )

    store.add(candle)

    return {
        "status": "stored",
        "symbol": candle.symbol,
        "timeframe": candle.timeframe,
        "timestamp": (
            candle.timestamp.isoformat()
        ),
        "count": store.count(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
        ),
    }


@router.post(
    "/analyze",
)
def analyze_live_market(
    payload: LiveMarketAnalysisRequest,
    request: Request,
) -> dict[str, object]:
    store = get_live_store(
        request
    )

    symbol = payload.symbol.strip()
    timeframe = payload.timeframe.strip()

    candles = store.get_latest(
        symbol=symbol,
        timeframe=timeframe,
        limit=payload.candle_limit,
    )

    minimum_required = 50

    if len(candles) < minimum_required:
        raise HTTPException(
            status_code=400,
            detail=(
                "No hay suficientes velas "
                f"para analizar {symbol} "
                f"en {timeframe}. "
                f"Se requieren al menos "
                f"{minimum_required} velas "
                f"y existen {len(candles)}."
            ),
        )

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
                    payload.account_balance
                ),
                risk_percent=(
                    payload.risk_percent
                ),
                reward_risk_ratio=(
                    payload.reward_risk_ratio
                ),
                point_value=(
                    payload.point_value
                ),
            ),
            DecisionStage(
                reward_risk_ratio=(
                    payload.reward_risk_ratio
                ),
            ),
        ]
    )

    context = pipeline.run(
        initial_context={
            "symbol": symbol,
            "timeframe": timeframe,
            "backtest_candles": candles,
        }
    )

    return TradingCopilotService().build_context(
        context
    )
