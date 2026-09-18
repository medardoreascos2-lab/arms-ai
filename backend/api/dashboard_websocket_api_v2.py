from __future__ import annotations

from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from backend.api.admin_authorization_dependency_v2 import (
    ADMIN_TOKEN_HEADER,
)
from backend.security.admin_authorization_v2 import (
    AdminAuthorizationV2,
)
from backend.api.dashboard_browser_transport_v11 import browser_admin_token, dashboard_snapshot


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

        authority = getattr(
            websocket.app.state,
            "admin_authorization_v2",
            None,
        )

        if not isinstance(
            authority,
            AdminAuthorizationV2,
        ):
            await websocket.close(
                code=1008,
            )
            return

        try:
            authority.require_authorized(
                browser_admin_token(websocket, ADMIN_TOKEN_HEADER)
            )
        except PermissionError:
            await websocket.close(
                code=1008,
            )
            return

        if websocket_hub_v2 is None:
            await websocket.close()
            return

        if 'arms-dashboard-v1' in websocket.scope.get('subprotocols', []):
            await websocket_hub_v2.connect(websocket=websocket, subprotocol='arms-dashboard-v1')
        else:
            await websocket_hub_v2.connect(websocket=websocket)

        try:
            snapshot = (
                dashboard_snapshot(websocket.app.state, live_data_service_v2)
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
                await websocket.receive_text()

        except WebSocketDisconnect:
            pass

        finally:
            websocket_hub_v2.disconnect(
                websocket=websocket,
            )

    return router
