from fastapi import FastAPI

from backend.api.error_handlers import (
    register_exception_handlers,
)
from backend.api.logging_middleware import (
    register_logging_middleware,
)
from backend.api.routers.portfolio import (
    router as portfolio_router,
)
from backend.config.api_settings import (
    APISettings,
)


def create_app(
    settings: APISettings | None = None,
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

    app = FastAPI(
        title=settings.title,
        version=settings.version,
        debug=settings.debug,
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

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "arms-ai-api",
        }

    return app


app = create_app()
