from time import perf_counter

from fastapi import FastAPI, Request

from backend.config.logging_config import (
    configure_logging,
)


def register_logging_middleware(
    app: FastAPI,
) -> None:
    logger = configure_logging()

    @app.middleware("http")
    async def log_requests(
        request: Request,
        call_next,
    ):
        started_at = perf_counter()

        response = await call_next(
            request
        )

        elapsed_ms = (
            perf_counter()
            - started_at
        ) * 1000.0

        logger.info(
            "%s %s -> %s %.2f ms",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
