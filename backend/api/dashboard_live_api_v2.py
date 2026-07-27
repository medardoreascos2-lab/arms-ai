from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException

from datetime import datetime
from datetime import timezone


def create_dashboard_live_router_v2(
    *,
    live_data_service_v2=None,
) -> APIRouter:

    if (
        live_data_service_v2
        is not None
        and not callable(
            getattr(
                live_data_service_v2,
                "get_snapshot",
                None,
            )
        )
    ):
        raise TypeError(
            "live_data_service_v2 debe implementar "
            "get_snapshot()."
        )

    router = APIRouter(
        prefix="/api/v2",
        tags=["Dashboard Live V2"],
    )

    @router.get(
        "/dashboard/live",
    )
    def get_dashboard_live():

        if live_data_service_v2 is None:
            return {
                "snapshot_time": (
                    datetime.now(
                        timezone.utc
                    ).isoformat()
                ),
                "dashboard_status": "EMPTY",
            }

        try:
            return (
                live_data_service_v2
                .get_snapshot()
            )

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "dashboard_live_snapshot_failed"
                ),
            ) from exc

    return router
