from fastapi import APIRouter, Query, Request

from backend.dashboard.execution_manager_read_projection_v2 import (
    project_execution_manager,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=["Execution Manager"],
)


@router.get("/execution-manager")
def execution_manager_dashboard(
    request: Request,
    symbol: str | None = Query(default=None, min_length=1),
    timeframe: str | None = Query(default=None, min_length=1),
):
    """Observe an existing prepared order; this route has no execution engine."""
    return project_execution_manager(
        store=getattr(request.app.state, "live_analysis_store", None),
        symbol=symbol,
        timeframe=timeframe,
    )
