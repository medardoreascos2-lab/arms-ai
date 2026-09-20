"""Explicitly injected current PAPER service; no broker or feed auto-discovery."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.admin_authorization_dependency_v2 import require_admin_authorization_v2
from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.security.admin_authorization_v2 import AdminAuthorizationV2


def create_current_paper_app_v1(*, service, admin_token=None, dashboard_origin="http://localhost:3000"):
    if type(service) is not CurrentPaperServiceV1:
        raise TypeError("explicit isolated current PAPER service required")

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.shutdown()

    app = FastAPI(title="ARMS AI current SIMULATED / PAPER", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[dashboard_origin], allow_methods=["GET", "POST"],
                       allow_headers=["X-ARMS-ADMIN-TOKEN", "Content-Type"])
    if admin_token:
        app.state.admin_authorization_v2 = AdminAuthorizationV2(token=admin_token)

    @app.get("/health")
    def health():
        return {"status": "PROCESS_HEALTHY", "mode": "CURRENT_MARKET_PAPER", "live_execution_allowed": False}

    @app.get("/api/v2/paper/readiness")
    def readiness():
        snap = service.get_snapshot()
        return {k: snap[k] for k in ("mode", "config_hash", "paper_ready", "readiness_reasons")}

    @app.get("/api/v2/backtesting/dashboard")
    def dashboard():
        return {"paper_research": service.get_snapshot()}

    @app.post("/api/v2/paper/{command}", dependencies=[Depends(require_admin_authorization_v2)])
    def command(command: str):
        try:
            if command == "shutdown":
                service.shutdown()
                return service.get_snapshot()
            return service.control(command)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from None

    # Data arrives through the explicitly configured in-process provider adapter,
    # never through dashboard GET, websocket subscription or an unauthenticated POST.
    return app
