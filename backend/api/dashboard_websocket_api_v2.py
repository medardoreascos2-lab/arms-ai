from __future__ import annotations

import asyncio

from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect


def create_dashboard_websocket_router_v2(
    *,
    websocket_hub_v2=None,
    live_data_service_v2=None,
) -> APIRouter:

    if (
        websocket_hub_v2 is not None
        and (
            not callable(
                getattr(
                    websocket_hub_v2,
                    "connect",
                    None,
                )
            )
            or not callable(
                getattr(
                    websocket_hub_v2,
                    "disconnect",
                    None,
                )
            )
        )
    ):
        raise TypeError(
            "websocket_hub_v2 debe implementar "
            "connect() y disconnect()."
        )

    if (
        live_data_service_v2 is not None
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
        tags=[
            "Dashboard WebSocket V2",
        ],
    )

    @router.websocket(
        "/dashboard/ws",
    )
    async def dashboard_websocket(
        websocket: WebSocket,
    ) -> None:

        if websocket_hub_v2 is None:
            await websocket.close()
            return

        await websocket_hub_v2.connect(
            websocket=websocket,
        )

        try:
            snapshot = (
                live_data_service_v2.get_snapshot()
                if live_data_service_v2
                is not None
                else None
            )

            await websocket.send_json(
                {
                    "event_type": (
                        "dashboard_snapshot"
                    ),
                    "data": snapshot,
                }
            )

            while True:
                await asyncio.sleep(
                    3600
                )

        except WebSocketDisconnect:
            pass

        finally:
            websocket_hub_v2.disconnect(
                websocket=websocket,
            )

    return router
