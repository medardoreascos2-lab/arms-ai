"""Opt-in read-only smoke host. Bind the ASGI server to 127.0.0.1 only."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.market_data.ninjatrader_market_reader_v1 import NinjaTraderMarketReaderV1


def create_ninjatrader_market_app_v1(*, reader):
    if type(reader) is not NinjaTraderMarketReaderV1:
        raise TypeError("explicit audited market reader required")

    async def consume():
        while True:
            try:
                await asyncio.to_thread(reader.poll)
            except (ValueError, RuntimeError):
                return  # Gate latched; no automatic reconnect/restart.
            await asyncio.sleep(.25)

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(consume())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            reader.close()

    app = FastAPI(title="ARMS NinjaTrader READ-ONLY market smoke", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000"], allow_methods=["GET"])

    @app.get("/health")
    def health():
        return {"status": "PROCESS_HEALTHY", "external_order_authority": False}

    @app.get("/api/v2/paper/readiness")
    def readiness():
        return reader.get_snapshot()

    @app.get("/api/v2/backtesting/dashboard")
    def dashboard():
        return {"paper_research": reader.get_snapshot()}

    return app
