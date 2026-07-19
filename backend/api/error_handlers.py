from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def register_exception_handlers(
    app: FastAPI,
) -> None:
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

    @app.exception_handler(
        RequestValidationError
    )
    async def request_validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "type": (
                        "RequestValidationError"
                    ),
                    "message": str(exc),
                }
            },
        )
