from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone


class DashboardAutoRefreshEngineV2:

    def __init__(
        self,
        *,
        event_bus_v2=None,
        event_dispatcher_v2=None,
        refresh_service_v2=None,
    ) -> None:

        if (
            event_bus_v2 is not None
            and not callable(
                getattr(
                    event_bus_v2,
                    "publish",
                    None,
                )
            )
        ):
            raise TypeError(
                "event_bus_v2 debe implementar publish()."
            )

        if (
            event_dispatcher_v2 is not None
            and not callable(
                getattr(
                    event_dispatcher_v2,
                    "register",
                    None,
                )
            )
        ):
            raise TypeError(
                "event_dispatcher_v2 debe implementar register()."
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

        self.event_bus_v2 = event_bus_v2
        self.event_dispatcher_v2 = event_dispatcher_v2
        self.refresh_service_v2 = refresh_service_v2

        self._state = {
            "started": False,
            "start_count": 0,
            "last_start_time": None,
            "last_registration": None,
            "last_initial_refresh": None,
        }

    def start(
        self,
    ) -> dict[str, object]:

        registration = None

        if self.event_dispatcher_v2 is not None:
            registration = (
                self.event_dispatcher_v2.register()
            )

        refresh_result = None

        if self.refresh_service_v2 is not None:
            refresh_result = (
                self.refresh_service_v2.refresh(
                    reason="initial_startup",
                    event={
                        "event_type": "dashboard_refresh",
                        "payload": {},
                    },
                )
            )

        start_time = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self._state["started"] = True
        self._state["start_count"] += 1
        self._state["last_start_time"] = start_time
        self._state["last_registration"] = registration
        self._state["last_initial_refresh"] = refresh_result

        return {
            "started": True,
            "registered": registration is not None,
            "subscription_count": (
                registration.get(
                    "subscription_count",
                    0,
                )
                if registration
                else 0
            ),
            "initial_refresh": (
                refresh_result is not None
            ),
            "start_count": self._state[
                "start_count"
            ],
        }

    def publish_event(
        self,
        *,
        event_type: str,
        payload: dict[str, object],
    ) -> dict[str, object]:

        if (
            not isinstance(
                event_type,
                str,
            )
            or not event_type.strip()
        ):
            raise ValueError(
                "event_type inválido."
            )

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "payload debe ser dict."
            )

        if self.event_bus_v2 is None:
            return {
                "published": False,
                "reason": "no_event_bus",
            }

        return self.event_bus_v2.publish(
            event_type=event_type,
            payload=payload,
        )

    def get_state(
        self,
    ) -> dict[str, object]:

        return deepcopy(
            self._state
        )
