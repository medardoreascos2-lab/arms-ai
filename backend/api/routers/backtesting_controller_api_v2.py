from __future__ import annotations

from fastapi import APIRouter


def create_backtesting_controller_router_v2(
    *,
    controller,
) -> APIRouter:
    """
    Router REST para consultar y controlar
    el subsistema de backtesting.
    """

    if (
        not callable(
            getattr(
                controller,
                "start",
                None,
            )
        )
        or not callable(
            getattr(
                controller,
                "stop",
                None,
            )
        )
        or not callable(
            getattr(
                controller,
                "status",
                None,
            )
        )
    ):
        raise TypeError(
            "controller debe implementar "
            "start(), stop() y status()."
        )

    router = APIRouter(
        prefix=(
            "/api/v2/backtesting/controller"
        ),
        tags=[
            "backtesting-controller-v2",
        ],
    )

    @router.get("/status")
    def get_status():

        return controller.status()

    @router.post("/start")
    def start_controller():

        was_running = bool(
            getattr(
                controller,
                "is_running",
                False,
            )
        )

        controller.start()

        return {
            "started": not was_running,
            "is_running": bool(
                getattr(
                    controller,
                    "is_running",
                    False,
                )
            ),
        }

    @router.post("/stop")
    def stop_controller():

        was_running = bool(
            getattr(
                controller,
                "is_running",
                False,
            )
        )

        controller.stop(
            timeout=5.0,
        )

        return {
            "stopped": was_running,
            "is_running": bool(
                getattr(
                    controller,
                    "is_running",
                    False,
                )
            ),
        }

    return router
