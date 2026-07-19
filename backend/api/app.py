from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api.routers.portfolio import router as portfolio_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ARMS AI API",
        version="1.0.0",
    )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exc: ValueError,
    ):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "type": "ValueError",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(TypeError)
    async def type_error_handler(
        request: Request,
        exc: TypeError,
    ):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "type": "TypeError",
                    "message": str(exc),
                }
            },
        )

    @app.exception_handler(TypeError)
    async def type_error_handler(
        request: Request,
        exc: TypeError,
    ):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "type": "TypeError",
                    "message": str(exc),
                }
            },
        )

    app.include_router(portfolio_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "arms-ai-api",
        }

    return app


app = create_app()
