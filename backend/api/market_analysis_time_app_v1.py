"""Explicit read-only dashboard app. No accounts, PAPER runtime or feed startup."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from contextlib import asynccontextmanager
from backend.market_data.analysis_time_profile_v1 import MarketAnalysisTimeProfileV1
from backend.market_data.fresh_native_adapter_v1 import FreshNativeAdapterV1


def create_market_analysis_time_app_v1(*, profile=None, adapter=None, dashboard_origin='http://localhost:3000'):
    if not ((type(profile) is MarketAnalysisTimeProfileV1 and adapter is None)
            or (profile is None and type(adapter) is FreshNativeAdapterV1)):
        raise TypeError('explicit analysis-only profile required')

    @asynccontextmanager
    async def lifespan(app):
        async def tail():
            try:
                while True:
                    await asyncio.to_thread(adapter.poll)
                    await asyncio.sleep(.25)
            except asyncio.CancelledError:
                raise
            except Exception:
                adapter.revoke('ADAPTER_WORKER_FAILED')
        task = asyncio.create_task(tail()) if adapter is not None else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                adapter.close()

    app=FastAPI(title='ARMS source-relative market observations',docs_url=None,redoc_url=None,lifespan=lifespan)
    app.add_middleware(CORSMiddleware,allow_origins=[dashboard_origin],allow_methods=['GET'],allow_headers=['Accept'])

    @app.get('/api/v2/market-analysis/time-profile')
    def snapshot():
        return adapter.snapshot() if adapter is not None else profile.snapshot()

    return app
