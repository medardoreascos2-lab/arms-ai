from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="ARMS AI API",
        version="1.0.0",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "arms-ai-api",
        }

    return app


app = create_app()
