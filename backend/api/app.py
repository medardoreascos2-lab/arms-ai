from fastapi import FastAPI

from backend.api.error_handlers import (
    register_exception_handlers,
)
from backend.api.routers.portfolio import (
    router as portfolio_router,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ARMS AI API",
        version="1.0.0",
    )

    register_exception_handlers(
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
