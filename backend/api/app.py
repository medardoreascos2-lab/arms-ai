from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
from backend.services.live_candle_store import (
    LiveCandleStore,
)


def create_app(
    settings: APISettings | None = None,
    live_candle_store: LiveCandleStore
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

    app = FastAPI(
        title=settings.title,
        version=settings.version,
        debug=settings.debug,
    )

    app.state.live_candle_store = (
        live_candle_store
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
