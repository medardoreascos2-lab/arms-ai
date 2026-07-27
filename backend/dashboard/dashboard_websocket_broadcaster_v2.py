from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone


class DashboardWebSocketBroadcasterV2:

    def __init__(
        self,
        *,
        refresh_service_v2=None,
        websocket_hub_v2=None,
    ) -> None:

        if (
            refresh_service_v2
            is not None
            and (
                not callable(
                    getattr(
                        refresh_service_v2,
                        "get_cached_snapshot",
                        None,
                    )
                )
                or not callable(
                    getattr(
                        refresh_service_v2,
                        "get_cached_widgets",
                        None,
                    )
                )
            )
        ):
            raise TypeError(
                "refresh_service_v2 debe implementar "
                "get_cached_snapshot() y "
                "get_cached_widgets()."
            )

        if (
            websocket_hub_v2
            is not None
            and not callable(
                getattr(
                    websocket_hub_v2,
                    "broadcast",
                    None,
                )
            )
        ):
            raise TypeError(
                "websocket_hub_v2 debe implementar "
                "broadcast()."
            )

        self.refresh_service_v2 = (
            refresh_service_v2
        )

        self.websocket_hub_v2 = (
            websocket_hub_v2
        )

    async def broadcast_update(
        self,
        *,
        reason: str,
        event: dict[str, object],
    ) -> dict[str, object]:

        if (
            not isinstance(
                reason,
                str,
            )
            or not reason.strip()
        ):
            raise ValueError(
                "reason inválido."
            )

        if not isinstance(
            event,
            dict,
        ):
            raise TypeError(
                "event debe ser un dict."
            )

        if self.websocket_hub_v2 is None:
            return {
                "broadcasted": False,
                "reason": "no_websocket_hub",
            }

        if self.refresh_service_v2 is None:
            return {
                "broadcasted": False,
                "reason": "no_refresh_service",
            }

        dashboard = (
            self.refresh_service_v2
            .get_cached_snapshot()
        )

        widgets = (
            self.refresh_service_v2
            .get_cached_widgets()
        )

        payload = {
            "event_type": "dashboard_updated",
            "broadcast_time": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "reason": reason,
            "dashboard": deepcopy(
                dashboard
            ),
            "widgets": deepcopy(
                widgets
            ),
            "source_event": deepcopy(
                event
            ),
        }

        result = await (
            self.websocket_hub_v2.broadcast(
                payload=payload,
            )
        )

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "websocket_hub_v2.broadcast() "
                "debe devolver un dict."
            )

        response = dict(
            result
        )

        response[
            "reason"
        ] = reason

        return response
