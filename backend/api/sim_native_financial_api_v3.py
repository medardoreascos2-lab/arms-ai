"""Read-only dependency; no financial service lifecycle or ingestion on GET."""
from fastapi import APIRouter, Response


def create_sim_native_financial_router_v3(read_snapshot, read_preflight=None, read_market_hours=None):
    router = APIRouter(tags=["SIM_NATIVE financial observations"])

    @router.get("/api/v3/dashboard/sim-native-financial")
    def financial(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return read_snapshot()

    if read_preflight is not None:
        @router.get("/api/v3/dashboard/sim-native-first-trade-preflight")
        def first_trade_preflight(response: Response):
            response.headers["Cache-Control"] = "no-store"
            return read_preflight()

    if read_market_hours is not None:
        @router.get("/api/v3/dashboard/sim-native-market-hours-authority")
        def market_hours_authority(response: Response):
            response.headers["Cache-Control"] = "no-store"
            return read_market_hours()

    return router
