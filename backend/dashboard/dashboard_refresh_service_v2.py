from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone


class DashboardRefreshServiceV2:

    def __init__(
        self,
        *,
        live_data_service_v2=None,
        widget_registry_v2=None,
    ) -> None:

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

        self.live_data_service_v2 = (
            live_data_service_v2
        )

        self.widget_registry_v2 = (
            widget_registry_v2
        )

        self._cached_snapshot = None
        self._cached_widgets = None

        self._state = {
            "refresh_count": 0,
            "last_refresh_time": None,
            "last_reason": None,
            "last_event": None,
        }

    def refresh(
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

        snapshot_updated = False
        widgets_updated = False

        if (
            self.live_data_service_v2
            is not None
        ):
            snapshot = (
                self.live_data_service_v2
                .get_snapshot()
            )

            if not isinstance(
                snapshot,
                dict,
            ):
                raise TypeError(
                    "get_snapshot() debe devolver "
                    "un dict."
                )

            self._cached_snapshot = deepcopy(
                snapshot
            )

            snapshot_updated = True

        if (
            self.widget_registry_v2
            is not None
        ):
            widgets = (
                self.widget_registry_v2
                .render_all()
            )

            if not isinstance(
                widgets,
                dict,
            ):
                raise TypeError(
                    "render_all() debe devolver "
                    "un dict."
                )

            self._cached_widgets = deepcopy(
                widgets
            )

            widgets_updated = True

        refresh_time = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        self._state[
            "refresh_count"
        ] += 1

        self._state[
            "last_refresh_time"
        ] = refresh_time

        self._state[
            "last_reason"
        ] = reason

        self._state[
            "last_event"
        ] = deepcopy(
            event
        )

        return {
            "refreshed": True,
            "reason": reason,
            "refresh_count": (
                self._state[
                    "refresh_count"
                ]
            ),
            "snapshot_updated":
                snapshot_updated,
            "widgets_updated":
                widgets_updated,
            "refresh_time":
                refresh_time,
        }

    def get_cached_snapshot(
        self,
    ) -> dict[str, object] | None:

        if (
            self._cached_snapshot
            is None
        ):
            return None

        return deepcopy(
            self._cached_snapshot
        )

    def get_cached_widgets(
        self,
    ) -> dict[str, object] | None:

        if (
            self._cached_widgets
            is None
        ):
            return None

        return deepcopy(
            self._cached_widgets
        )

    def get_state(
        self,
    ) -> dict[str, object]:

        return deepcopy(
            self._state
        )
