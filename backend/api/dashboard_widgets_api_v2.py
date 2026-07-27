from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException


def create_dashboard_widgets_router_v2(
    *,
    widget_registry_v2=None,
) -> APIRouter:

    if (
        widget_registry_v2
        is not None
        and not callable(
            getattr(
                widget_registry_v2,
                "render_all",
                None,
            )
        )
    ):
        raise TypeError(
            "widget_registry_v2 debe implementar "
            "render_all()."
        )

    router = APIRouter(
        prefix="/api/v2",
        tags=[
            "Dashboard Widgets V2",
        ],
    )

    @router.get(
        "/dashboard/widgets",
    )
    def get_dashboard_widgets():

        if widget_registry_v2 is None:
            return {
                "status": "EMPTY",
                "widget_count": 0,
                "widgets": {},
            }

        try:
            result = (
                widget_registry_v2
                .render_all()
            )

            if not isinstance(
                result,
                dict,
            ):
                raise TypeError(
                    "render_all() debe devolver "
                    "un dict."
                )

            return result

        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=(
                    "dashboard_widgets_render_failed"
                ),
            ) from exc

    return router
