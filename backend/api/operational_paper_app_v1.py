"""Read-only HTTP projections. Only the bounded launcher consumes the feed."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.backtesting.operational_paper_v1 import OperationalPaperV1


def create_operational_paper_app_v1(*, runtime):
    if type(runtime) is not OperationalPaperV1:
        raise TypeError('explicit local PAPER coordinator required')
    app = FastAPI(title='ARMS LOCAL PAPER observation', docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000', 'http://127.0.0.1:3000'],
                       allow_methods=['GET'], allow_credentials=False)

    @app.get('/health')
    def health():
        return dict(status='PROCESS_HEALTHY', execution_mode='LOCAL_PAPER', external_order_authority=False)

    @app.get('/api/v2/backtesting/dashboard')
    def dashboard():
        return dict(paper_research=runtime.get_snapshot())

    @app.get('/api/v2/paper/readiness')
    def readiness():
        return runtime.get_snapshot()

    return app
