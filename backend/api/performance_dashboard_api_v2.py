from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException


def create_performance_dashboard_router_v2(
    *,
    dashboard_engine_v2=None,
) -> APIRouter:

    if (
        dashboard_engine_v2
        is not None
        and not hasattr(
            dashboard_engine_v2,
            "build",
        )
    ):
        raise TypeError(
            "dashboard_engine_v2 debe implementar build()."
        )

    router = APIRouter(
        prefix="/api/v2",
        tags=["Performance Dashboard V2"],
    )

    @router.get(
        "/dashboard",
    )
    def get_dashboard():

        if dashboard_engine_v2 is None:
            return {
                "dashboard_status": "EMPTY",
                "account_state": None,
                "portfolio_summary": None,
                "trade_journal_summary": None,
                "analytics": None,
                "breakdown": None,
                "account_overview": None,
                "performance_overview": None,
                "risk_status": None,
            }

        try:
            return dashboard_engine_v2.build()

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="dashboard_build_failed",
            ) from exc

    return router
