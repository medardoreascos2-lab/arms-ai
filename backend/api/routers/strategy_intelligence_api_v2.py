from fastapi import APIRouter, Request

from backend.dashboard.strategy_intelligence_read_projection_v2 import (
    project_strategy_intelligence,
)


router = APIRouter(
    prefix="/api/v2/dashboard",
    tags=["Strategy Intelligence"],
)


@router.get("/strategy-intelligence")
def strategy_intelligence(request: Request):
    """Read completed reports from this application; never generate results."""
    return project_strategy_intelligence(
        job_manager=getattr(request.app.state, "backtesting_job_manager_v2", None),
        job_executor=getattr(request.app.state, "backtesting_job_executor_v2", None),
    )
