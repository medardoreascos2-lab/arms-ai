from __future__ import annotations

from datetime import datetime
from datetime import timezone


class DashboardEventBusV2:

    def __init__(
        self,
    ) -> None:

        self._subscribers: dict[
            str,
            list,
        ] = {}

        self._history: list[
            dict[str, object]
        ] = []

    def subscribe(
        self,
        *,
        event_type: str,
        listener,
    ) -> dict[str, object]:

        if not isinstance(
            event_type,
            str,
        ) or not event_type.strip():
            raise ValueError(
                "event_type inválido."
            )

        if not callable(
            listener,
        ):
            raise TypeError(
                "listener debe ser callable."
            )

        self._subscribers.setdefault(
            event_type,
            [],
        ).append(
            listener
        )

        return {
            "subscribed": True,
            "event_type": event_type,
        }

    def unsubscribe(
        self,
        *,
        event_type: str,
        listener,
    ) -> dict[str, object]:

        listeners = self._subscribers.get(
            event_type,
            [],
        )

        if listener in listeners:
            listeners.remove(
                listener
            )

            if not listeners:
                self._subscribers.pop(
                    event_type,
                    None,
                )

            return {
                "unsubscribed": True,
            }

        return {
            "unsubscribed": False,
        }

    def publish(
        self,
        *,
        event_type: str,
        payload: dict[str, object],
    ) -> dict[str, object]:

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "payload debe ser dict."
            )

        event = {
            "event_type": event_type,
            "event_time": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "payload": payload,
        }

        self._history.append(
            event
        )

        notified = 0
        errors = 0

        for listener in self._subscribers.get(
            event_type,
            [],
        ):
            try:
                try:
                    listener(
                        event=event
                    )
                except TypeError:
                    listener(
                        event
                    )

                notified += 1

            except Exception:
                errors += 1

        return {
            "published": True,
            "listeners_notified": notified,
            "listener_errors": errors,
        }

    def get_subscriber_count(
        self,
    ) -> int:

        return sum(
            len(v)
            for v in self._subscribers.values()
        )

    def get_event_history(
        self,
    ) -> list[dict[str, object]]:

        return list(
            self._history
        )
