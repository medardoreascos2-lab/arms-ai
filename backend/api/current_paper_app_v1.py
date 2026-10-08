"""Explicitly injected current PAPER service; no broker or feed auto-discovery."""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.admin_authorization_dependency_v2 import require_admin_authorization_v2
from backend.backtesting.current_paper_runtime_v1 import CurrentPaperServiceV1
from backend.security.admin_authorization_v2 import AdminAuthorizationV2
from backend.market_data.sim_binding_contract_v1 import native_sim_status


def _operator_observation(service):
    """One detached read model; this function has no control-plane access."""
    snapshot = service.get_snapshot()
    trace = service.get_decision_trace(limit=1)
    records = trace.get("records") if isinstance(trace, dict) else None
    latest_trace = records[0] if isinstance(records, list) and records else None
    latest = latest_trace if isinstance(latest_trace, dict) else (
        snapshot.get("latest_decision")
        if isinstance(snapshot.get("latest_decision"), dict) else {})
    metadata = latest.get("decision_metadata")
    if not isinstance(metadata, dict):
        metadata = latest.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    submission = latest.get("submission_outcome")
    blocking = (submission.get("blocking_reasons")
                if isinstance(submission, dict) else None)
    if not isinstance(blocking, list):
        blocking = latest.get("progression_readiness_reasons")
    if not isinstance(blocking, list):
        blocking = snapshot.get("readiness_reasons")
    account = snapshot.get("account_overview")
    account = account if isinstance(account, dict) else {}
    positions = snapshot.get("active_simulated_positions")
    positions = positions if isinstance(positions, list) else []
    risk = snapshot.get("risk_evaluation")
    return {
        "mode": "CURRENT_MARKET_PAPER",
        "market_state": {
            "market_data": snapshot.get("market_data"),
            "session": snapshot.get("session_state"),
            "freshness": snapshot.get("data_freshness"),
        },
        "latest_decision": {
            "action": latest.get("action"),
            "confidence": latest.get("confidence"),
            "confluence": latest.get("confluence_score",
                metadata.get("confluence_score")),
            "trade_quality": latest.get("trade_quality_score"),
            "blocking_reasons": list(blocking or []),
            "reason": latest.get("decision_reason", latest.get("reason")),
        },
        "paper_ready": snapshot.get("paper_ready") is True,
        "paper_execution_enabled": (
            snapshot.get("paper_execution_enabled") is True),
        "simulated_open_positions": positions,
        "completed_simulated_trades": snapshot.get("completed_trades", 0),
        "realized_pnl": account.get("realized_pnl"),
        "unrealized_pnl": account.get("unrealized_pnl"),
        "decision_trace_count": trace.get("total", 0),
        "current_risk_status": {
            "dashboard_status": snapshot.get("dashboard_status"),
            "paper_authority_state": snapshot.get("paper_authority_state"),
            "readiness_reasons": snapshot.get("readiness_reasons"),
            "risk_evaluation": risk if isinstance(risk, dict) else None,
        },
        "live_execution_allowed": snapshot.get("live_execution_allowed"),
        "external_order_authority": snapshot.get("external_order_authority"),
        "broker_live_order_authority": snapshot.get(
            "broker_live_order_authority"),
        "ninjatrader_control_authority": snapshot.get(
            "ninjatrader_control_authority"),
        "read_only": True,
    }


def create_current_paper_app_v1(*, service, admin_token=None,
                                dashboard_origin="http://localhost:3000",
                                runtime_health_provider=None):
    if type(service) is not CurrentPaperServiceV1:
        raise TypeError("explicit isolated current PAPER service required")

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.shutdown()

    app = FastAPI(title="ARMS AI current SIMULATED / PAPER", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=[dashboard_origin], allow_methods=["GET", "POST"],
                       allow_headers=["X-ARMS-ADMIN-TOKEN", "X-ARMS-REQUEST-ID",
                                      "X-ARMS-REQUEST-NONCE", "Content-Type"])
    if admin_token:
        app.state.admin_authorization_v2 = AdminAuthorizationV2(token=admin_token)

    @app.get("/health")
    def health():
        lifecycle = (runtime_health_provider()
                     if callable(runtime_health_provider) else None)
        snapshot = service.get_snapshot()
        return {
            "status": "PROCESS_HEALTHY",
            "mode": "CURRENT_MARKET_PAPER",
            "runtime_lifecycle": lifecycle,
            "paper_execution_enabled": snapshot.get(
                "paper_execution_enabled"),
            "live_execution_allowed": snapshot.get(
                "live_execution_allowed"),
            "external_order_authority": snapshot.get(
                "external_order_authority"),
            "broker_live_order_authority": snapshot.get(
                "broker_live_order_authority"),
            "ninjatrader_control_authority": snapshot.get(
                "ninjatrader_control_authority"),
        }

    @app.get("/api/v2/paper/readiness")
    def readiness():
        snap = service.get_snapshot()
        return {k: snap[k] for k in ("mode", "config_hash", "paper_ready", "readiness_reasons")}

    @app.get("/api/v2/backtesting/dashboard")
    def dashboard():
        return {"paper_research": {**service.get_snapshot(), **native_sim_status()}}

    @app.get("/api/v2/paper/operator-observation")
    def operator_observation():
        return _operator_observation(service)

    @app.get("/api/v2/paper/sim-readiness")
    def sim_readiness():
        return native_sim_status()

    @app.post("/api/v2/paper/{command}", dependencies=[Depends(require_admin_authorization_v2)])
    def command(command: str,
                request_id: str = Header(default=None,alias='X-ARMS-REQUEST-ID'),
                request_nonce: str = Header(default=None,alias='X-ARMS-REQUEST-NONCE')):
        try:
            if command == "shutdown":
                service.shutdown(reason='OPERATOR_REQUEST',
                    initiating_path='PAPER_API',)
                return service.get_snapshot()
            return service.control(command,request_id=request_id,
                request_nonce=request_nonce,
                initiating_path='PAPER_API')
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc)) from None

    # Data arrives through the explicitly configured in-process provider adapter,
    # never through dashboard GET, websocket subscription or an unauthenticated POST.
    return app
