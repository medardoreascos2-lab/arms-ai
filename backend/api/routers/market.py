from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    status,
)

from backend.api.schemas.market import (
    LiveMarketAnalysisRequest,
    MarketWebhookRequest,
)
from backend.models.candle import Candle
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)


router = APIRouter(
    prefix="/market",
    tags=["market"],
)


def get_live_analysis_store(
    request: Request,
) -> LiveAnalysisStore:
    store = request.app.state.live_analysis_store

    if not isinstance(
        store,
        LiveAnalysisStore,
    ):
        raise RuntimeError(
            "LiveAnalysisStore no está configurado."
        )

    return store


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

    analysis_generated = False

    analysis_store = get_live_analysis_store(
        request
    )

    service = LiveMarketAnalysisService(
        candle_store=store,
        analysis_store=analysis_store,
    )

    if service.can_analyze(
        symbol=candle.symbol,
        timeframe=candle.timeframe,
    ):
        service.analyze(
            symbol=candle.symbol,
            timeframe=candle.timeframe,
            candle_limit=50,
            account_balance=17000.0,
            risk_percent=0.5,
            point_value=2.0,
            reward_risk_ratio=2.0,
        )

        analysis_generated = True

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
        "analysis_generated": analysis_generated,
    }


@router.post(
    "/analyze",
)
def analyze_live_market(
    payload: LiveMarketAnalysisRequest,
    request: Request,
) -> dict[str, object]:
    candle_store = get_live_store(
        request
    )

    analysis_store = get_live_analysis_store(
        request
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
    )

    try:
        return service.analyze(
            symbol=payload.symbol.strip(),
            timeframe=payload.timeframe.strip(),
            candle_limit=payload.candle_limit,
            account_balance=payload.account_balance,
            risk_percent=payload.risk_percent,
            point_value=payload.point_value,
            reward_risk_ratio=(
                payload.reward_risk_ratio
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error


@router.get("/latest-analysis")
def get_latest_market_analysis(
    request: Request,
    symbol: str = Query(
        ...,
        min_length=1,
    ),
    timeframe: str = Query(
        ...,
        min_length=1,
    ),
) -> dict[str, object]:
    analysis_store = get_live_analysis_store(
        request
    )

    analysis = analysis_store.get_latest(
        symbol=symbol,
        timeframe=timeframe,
    )

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No existe un análisis disponible "
                f"para {symbol} "
                f"en {timeframe}."
            ),
        )

    return analysis
