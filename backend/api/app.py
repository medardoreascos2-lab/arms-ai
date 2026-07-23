from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.account_risk.account_risk_guard import (
    AccountRiskGuard,
)
from backend.api.error_handlers import (
    register_exception_handlers,
)
from backend.api.logging_middleware import (
    register_logging_middleware,
)
from backend.api.routers.ai import (
    router as ai_router,
)
from backend.api.routers.market import (
    router as market_router,
)
from backend.api.routers.portfolio import (
    router as portfolio_router,
)
from backend.config.api_settings import (
    APISettings,
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
from backend.services.live_analysis_store import (
    LiveAnalysisStore,
)
from backend.services.live_candle_store import (
    LiveCandleStore,
)
from backend.services.live_signal_store import (
    LiveSignalStore,
)
from backend.services.signal_history_store import (
    SignalHistoryStore,
)
from backend.risk_management.position_sizing_engine import (
    PositionSizingEngine,
)
from backend.services.trade_history_store import (
    TradeHistoryStore,
)


def create_app(
    settings: APISettings | None = None,
    live_candle_store: LiveCandleStore
    | None = None,
    live_analysis_store: LiveAnalysisStore
    | None = None,
    live_signal_store: LiveSignalStore
    | None = None,
    signal_history_store: SignalHistoryStore
    | None = None,
    signal_execution_manager:
    SignalExecutionManager
    | None = None,
    trade_execution_engine:
    TradeExecutionEngine
    | None = None,
    position_manager:
    PositionManager
    | None = None,
    trade_history_store:
    TradeHistoryStore
    | None = None,
    account_risk_guard:
    AccountRiskGuard
    | None = None,
    position_sizing_engine:
    PositionSizingEngine
    | None = None,
) -> FastAPI:
    if settings is None:
        settings = APISettings()

    if not isinstance(
        settings,
        APISettings,
    ):
        raise TypeError(
            "settings debe ser APISettings."
        )

    if live_candle_store is None:
        live_candle_store = (
            LiveCandleStore()
        )

    if not isinstance(
        live_candle_store,
        LiveCandleStore,
    ):
        raise TypeError(
            "live_candle_store debe ser "
            "LiveCandleStore."
        )

    if live_analysis_store is None:
        live_analysis_store = (
            LiveAnalysisStore()
        )

    if not isinstance(
        live_analysis_store,
        LiveAnalysisStore,
    ):
        raise TypeError(
            "live_analysis_store debe ser "
            "LiveAnalysisStore."
        )

    if live_signal_store is None:
        live_signal_store = (
            LiveSignalStore()
        )

    if not isinstance(
        live_signal_store,
        LiveSignalStore,
    ):
        raise TypeError(
            "live_signal_store debe ser "
            "LiveSignalStore."
        )

    if signal_history_store is None:
        signal_history_store = (
            SignalHistoryStore()
        )

    if not isinstance(
        signal_history_store,
        SignalHistoryStore,
    ):
        raise TypeError(
            "signal_history_store debe ser "
            "SignalHistoryStore."
        )

    if signal_execution_manager is None:
        signal_execution_manager = (
            SignalExecutionManager(
                cooldown_minutes=15
            )
        )

    if not isinstance(
        signal_execution_manager,
        SignalExecutionManager,
    ):
        raise TypeError(
            "signal_execution_manager debe ser "
            "SignalExecutionManager."
        )

    if trade_execution_engine is None:
        trade_execution_engine = (
            TradeExecutionEngine(
                mode="SIMULATED"
            )
        )

    if not isinstance(
        trade_execution_engine,
        TradeExecutionEngine,
    ):
        raise TypeError(
            "trade_execution_engine debe ser "
            "TradeExecutionEngine."
        )

    if position_manager is None:
        position_manager = (
            PositionManager()
        )

    if not isinstance(
        position_manager,
        PositionManager,
    ):
        raise TypeError(
            "position_manager debe ser "
            "PositionManager."
        )

    if trade_history_store is None:
        trade_history_store = (
            TradeHistoryStore()
        )

    if not isinstance(
        trade_history_store,
        TradeHistoryStore,
    ):
        raise TypeError(
            "trade_history_store debe ser "
            "TradeHistoryStore."
        )

    if account_risk_guard is None:
        account_risk_guard = (
            AccountRiskGuard(
                daily_loss_limit=3000.0,
                max_trades_per_day=4,
                max_consecutive_losses=3,
                max_open_positions=1,
                max_risk_per_trade=250.0,
            )
        )

    if not isinstance(
        account_risk_guard,
        AccountRiskGuard,
    ):
        raise TypeError(
            "account_risk_guard debe ser "
            "AccountRiskGuard."
        )

    if position_sizing_engine is None:
        position_sizing_engine = (
            PositionSizingEngine(
                minimum_contracts=1,
                maximum_contracts=20,
            )
        )

    if not isinstance(
        position_sizing_engine,
        PositionSizingEngine,
    ):
        raise TypeError(
            "position_sizing_engine debe ser "
            "PositionSizingEngine."
        )

    app = FastAPI(
        title=settings.title,
        version=settings.version,
        debug=settings.debug,
    )

    app.state.live_candle_store = (
        live_candle_store
    )

    app.state.live_analysis_store = (
        live_analysis_store
    )

    app.state.live_signal_store = (
        live_signal_store
    )

    app.state.signal_history_store = (
        signal_history_store
    )

    app.state.signal_execution_manager = (
        signal_execution_manager
    )

    app.state.trade_execution_engine = (
        trade_execution_engine
    )

    app.state.position_manager = (
        position_manager
    )

    app.state.trade_history_store = (
        trade_history_store
    )

    app.state.account_risk_guard = (
        account_risk_guard
    )

    app.state.position_sizing_engine = (
        position_sizing_engine
    )

    app.state.webhook_token = (
        settings.webhook_token
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(
        app
    )

    register_logging_middleware(
        app
    )

    app.include_router(
        portfolio_router
    )

    app.include_router(
        ai_router
    )

    app.include_router(
        market_router
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "arms-ai-api",
        }

    return app


app = create_app()
