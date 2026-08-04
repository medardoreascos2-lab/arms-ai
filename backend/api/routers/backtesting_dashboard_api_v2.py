from __future__ import annotations

from fastapi import APIRouter


def create_backtesting_dashboard_router_v2(
    *,
    controller,
) -> APIRouter:
    """
    Router REST para exponer un resumen
    del subsistema de backtesting.
    """

    if not callable(
        getattr(
            controller,
            "status",
            None,
        )
    ):
        raise TypeError(
            "controller debe implementar status()."
        )

    router = APIRouter(
        prefix="/api/v2/backtesting",
        tags=[
            "backtesting-dashboard-v2",
        ],
    )

    @router.get("/dashboard")
    def get_dashboard():

        return {
            "controller": (
                controller.status()
            ),
        }

    return router
