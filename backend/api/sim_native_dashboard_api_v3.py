"""Independent read-only heartbeat route; same public GET convention as Dashboard V2."""
from fastapi import APIRouter, Response
from backend.services.sim_native_dashboard_reader_v3 import SimNativeDashboardReaderV3


def create_sim_native_dashboard_router_v3(*, reader=None):
    reader = reader or SimNativeDashboardReaderV3()
    router = APIRouter(tags=["SIM_NATIVE observations"])

    @router.get("/api/v3/dashboard/sim-native-runtime")
    def sim_native_runtime(response: Response):
        response.headers["Cache-Control"] = "no-store"
        return reader.get_snapshot()

    return router
