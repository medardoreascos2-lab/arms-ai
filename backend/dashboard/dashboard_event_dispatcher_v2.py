from __future__ import annotations

import asyncio


class DashboardEventDispatcherV2:

    DEFAULT_EVENT_TYPES = (
        "trade_opened",
        "trade_closed",
        "position_updated",
        "portfolio_updated",
        "risk_updated",
        "dashboard_refresh",
    )

    def __init__(
        self,
        *,
        event_bus_v2=None,
        refresh_service_v2=None,
        websocket_broadcaster_v2=None,
    ) -> None:

        if (
            event_bus_v2 is not None
            and not callable(
                getattr(
                    event_bus_v2,
                    "subscribe",
                    None,
                )
            )
        ):
            raise TypeError(
                "event_bus_v2 debe implementar subscribe()."
            )

        if (
            refresh_service_v2 is not None
            and not callable(
                getattr(
                    refresh_service_v2,
                    "refresh",
                    None,
                )
            )
        ):
            raise TypeError(
                "refresh_service_v2 debe implementar refresh()."
            )

        if (
            websocket_broadcaster_v2 is not None
            and not callable(
                getattr(
                    websocket_broadcaster_v2,
                    "broadcast_update",
                    None,
                )
            )
        ):
            raise TypeError(
                "websocket_broadcaster_v2 debe implementar broadcast_update()."
            )

        self.event_bus_v2 = event_bus_v2
        self.refresh_service_v2 = refresh_service_v2
        self.websocket_broadcaster_v2 = (
            websocket_broadcaster_v2
        )

    def register(
        self,
    ) -> dict[str, object]:

        if self.event_bus_v2 is None:
            return {
                "registered": False,
                "subscription_count": 0,
            }

        subscription_count = 0

        for event_type in self.DEFAULT_EVENT_TYPES:

            result = self.event_bus_v2.subscribe(
                event_type=event_type,
                listener=self.dispatch,
            )

            if (
                isinstance(result, dict)
                and result.get("subscribed") is True
            ):
                subscription_count += 1

        return {
            "registered": True,
            "subscription_count": subscription_count,
        }

    def dispatch(
        self,
        *,
        event,
    ) -> dict[str, object]:

        if not isinstance(event, dict):
            raise TypeError(
                "event debe ser un dict."
            )

        event_type = event.get(
            "event_type"
        )

        if (
            not isinstance(event_type, str)
            or not event_type.strip()
        ):
            raise ValueError(
                "event_type inválido."
            )

        if self.refresh_service_v2 is None:
            return {
                "dispatched": False,
                "reason": "no_refresh_service",
            }

        self.refresh_service_v2.refresh(
            reason=event_type,
            event=event,
        )

        broadcast_scheduled = False
        broadcast_error = False

        if (
            self.websocket_broadcaster_v2
            is not None
        ):
            try:
                asyncio.run(
                    self.websocket_broadcaster_v2.broadcast_update(
                        reason=event_type,
                        event=event,
                    )
                )
                broadcast_scheduled = True

            except Exception:
                broadcast_error = True

        return {
            "dispatched": True,
            "reason": event_type,
            "broadcast_scheduled":
                broadcast_scheduled,
            "broadcast_error":
                broadcast_error,
        }
