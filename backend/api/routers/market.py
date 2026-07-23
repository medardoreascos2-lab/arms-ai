from secrets import compare_digest

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)

from backend.api.schemas.market import (
    LiveMarketAnalysisRequest,
    MarketWebhookRequest,
)
from backend.execution.position_manager import (
    PositionManager,
)
from backend.execution.signal_execution_manager import (
    SignalExecutionManager,
)
from backend.execution.trade_execution_engine import (
    TradeExecutionEngine,
)
from backend.models.candle import Candle
from backend.services.account_performance_service import (
    AccountPerformanceService,
)
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_market_analysis_service import (
    LiveMarketAnalysisService,
)
from backend.services.live_signal_store import (
    LiveSignalStore,
)
from backend.services.signal_history_store import (
    SignalHistoryStore,
)
from backend.services.trade_history_store import (
    TradeHistoryStore,
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
    x_arms_token: str | None = Header(
        default=None,
        alias="X-ARMS-TOKEN",
    ),
) -> dict[str, object]:
    expected_token = str(
        request.app.state.webhook_token
    )

    if (
        x_arms_token is None
        or not compare_digest(
            x_arms_token,
            expected_token,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de webhook inválido.",
        )

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

    signal_store = get_live_signal_store(
        request
    )

    signal_history_store = (
        get_signal_history_store(
            request
        )
    )

    execution_manager = (
        get_signal_execution_manager(
            request
        )
    )

    trade_execution_engine = (
        get_trade_execution_engine(
            request
        )
    )

    position_manager = (
        get_position_manager(
            request
        )
    )

    service = LiveMarketAnalysisService(
        candle_store=store,
        analysis_store=analysis_store,
        signal_store=signal_store,
        signal_history_store=(
            signal_history_store
        ),
        execution_manager=(
            execution_manager
        ),
        trade_execution_engine=(
            trade_execution_engine
        ),
        position_manager=(
            position_manager
        ),
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

    signal_store = get_live_signal_store(
        request
    )

    signal_history_store = (
        get_signal_history_store(
            request
        )
    )

    execution_manager = (
        get_signal_execution_manager(
            request
        )
    )

    trade_execution_engine = (
        get_trade_execution_engine(
            request
        )
    )

    position_manager = (
        get_position_manager(
            request
        )
    )

    service = LiveMarketAnalysisService(
        candle_store=candle_store,
        analysis_store=analysis_store,
        signal_store=signal_store,
        signal_history_store=(
            signal_history_store
        ),
        execution_manager=(
            execution_manager
        ),
        trade_execution_engine=(
            trade_execution_engine
        ),
        position_manager=(
            position_manager
        ),
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


def get_trade_history_store(
    request: Request,
) -> TradeHistoryStore:
    store = (
        request.app.state.trade_history_store
    )

    if not isinstance(
        store,
        TradeHistoryStore,
    ):
        raise RuntimeError(
            "TradeHistoryStore no está configurado."
        )

    return store


def get_position_manager(
    request: Request,
) -> PositionManager:
    manager = (
        request.app.state.position_manager
    )

    if not isinstance(
        manager,
        PositionManager,
    ):
        raise RuntimeError(
            "PositionManager no está configurado."
        )

    return manager


def get_trade_execution_engine(
    request: Request,
) -> TradeExecutionEngine:
    engine = (
        request.app.state.trade_execution_engine
    )

    if not isinstance(
        engine,
        TradeExecutionEngine,
    ):
        raise RuntimeError(
            "TradeExecutionEngine no está configurado."
        )

    return engine


def get_signal_execution_manager(
    request: Request,
) -> SignalExecutionManager:
    manager = (
        request.app.state.signal_execution_manager
    )

    if not isinstance(
        manager,
        SignalExecutionManager,
    ):
        raise RuntimeError(
            "SignalExecutionManager no está configurado."
        )

    return manager


def get_signal_history_store(
    request: Request,
) -> SignalHistoryStore:
    store = request.app.state.signal_history_store

    if not isinstance(
        store,
        SignalHistoryStore,
    ):
        raise RuntimeError(
            "SignalHistoryStore no está configurado."
        )

    return store


def get_live_signal_store(
    request: Request,
) -> LiveSignalStore:
    store = request.app.state.live_signal_store

    if not isinstance(
        store,
        LiveSignalStore,
    ):
        raise RuntimeError(
            "LiveSignalStore no está configurado."
        )

    return store


@router.get("/latest-signal")
def get_latest_market_signal(
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
    signal_store = get_live_signal_store(
        request
    )

    signal = signal_store.get_latest(
        symbol=symbol,
        timeframe=timeframe,
    )

    if signal is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No existe una señal disponible "
                f"para {symbol} "
                f"en {timeframe}."
            ),
        )

    return signal


@router.get("/signals")
def get_market_signal_history(
    request: Request,
    symbol: str = Query(
        ...,
        min_length=1,
    ),
    timeframe: str = Query(
        ...,
        min_length=1,
    ),
    limit: int = Query(
        50,
        ge=1,
        le=500,
    ),
) -> dict[str, object]:
    normalized_symbol = (
        symbol.strip().upper()
    )

    normalized_timeframe = (
        timeframe.strip().lower()
    )

    history_store = get_signal_history_store(
        request
    )

    signals = history_store.get_history(
        symbol=normalized_symbol,
        timeframe=normalized_timeframe,
        limit=limit,
    )

    return {
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "count": len(signals),
        "signals": signals,
    }



@router.get("/open-position")
def get_open_market_position(
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
    position_manager = get_position_manager(
        request
    )

    position = position_manager.get_open_position(
        symbol=symbol,
        timeframe=timeframe,
    )

    if position is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No existe una posición abierta "
                f"para {symbol} "
                f"en {timeframe}."
            ),
        )

    return position


@router.get("/performance")
def get_account_performance(
    request: Request,
    symbol: str = Query(
        ...,
        min_length=1,
    ),
    timeframe: str = Query(
        ...,
        min_length=1,
    ),
    starting_balance: float = Query(
        ...,
        gt=0,
    ),
) -> dict[str, object]:
    normalized_symbol = (
        symbol.strip().upper()
    )

    normalized_timeframe = (
        timeframe.strip().lower()
    )

    history_store = get_trade_history_store(
        request
    )

    trades = history_store.get_history(
        symbol=normalized_symbol,
        timeframe=normalized_timeframe,
        limit=500,
    )

    result = (
        AccountPerformanceService()
        .calculate(
            trades=trades,
            starting_balance=(
                starting_balance
            ),
        )
    )

    return {
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        **result,
    }


@router.get("/trades")
def get_trade_history(
    request: Request,
    symbol: str = Query(
        ...,
        min_length=1,
    ),
    timeframe: str = Query(
        ...,
        min_length=1,
    ),
    limit: int = Query(
        50,
        gt=0,
    ),
) -> dict[str, object]:
    history_store = get_trade_history_store(
        request
    )

    normalized_symbol = (
        symbol.strip().upper()
    )

    normalized_timeframe = (
        timeframe.strip().lower()
    )

    trades = history_store.get_history(
        symbol=normalized_symbol,
        timeframe=normalized_timeframe,
        limit=limit,
    )

    return {
        "symbol": normalized_symbol,
        "timeframe": normalized_timeframe,
        "count": len(trades),
        "trades": trades,
    }

