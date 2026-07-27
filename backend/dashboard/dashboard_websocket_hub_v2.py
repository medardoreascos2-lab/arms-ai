from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from datetime import timezone


class DashboardWebSocketHubV2:

    def __init__(
        self,
    ) -> None:

        self._connections = []

        self._state = {
            "connection_count": 0,
            "broadcast_count": 0,
            "messages_sent": 0,
            "send_errors": 0,
            "last_broadcast_time": None,
        }

    async def connect(
        self,
        *,
        websocket,
    ) -> dict[str, object]:

        if (
            not callable(
                getattr(
                    websocket,
                    "accept",
                    None,
                )
            )
            or not callable(
                getattr(
                    websocket,
                    "send_json",
                    None,
                )
            )
        ):
            raise TypeError(
                "websocket inválido."
            )

        if websocket in self._connections:
            return {
                "connected": False,
                "reason": "already_connected",
                "connection_count": len(
                    self._connections
                ),
            }

        await websocket.accept()

        self._connections.append(
            websocket
        )

        self._state[
            "connection_count"
        ] = len(
            self._connections
        )

        return {
            "connected": True,
            "connection_count": len(
                self._connections
            ),
        }

    def disconnect(
        self,
        *,
        websocket,
    ) -> dict[str, object]:

        if websocket not in self._connections:
            return {
                "disconnected": False,
                "reason": "not_connected",
            }

        self._connections.remove(
            websocket
        )

        self._state[
            "connection_count"
        ] = len(
            self._connections
        )

        return {
            "disconnected": True,
            "connection_count": len(
                self._connections
            ),
        }

    async def broadcast(
        self,
        *,
        payload: dict[str, object],
    ) -> dict[str, object]:

        if not isinstance(
            payload,
            dict,
        ):
            raise TypeError(
                "payload debe ser dict."
            )

        targeted = len(
            self._connections
        )

        sent = 0
        errors = 0

        for websocket in list(
            self._connections
        ):
            try:
                await websocket.send_json(
                    payload
                )

                sent += 1

            except Exception:
                errors += 1

                if websocket in self._connections:
                    self._connections.remove(
                        websocket
                    )

        self._state[
            "connection_count"
        ] = len(
            self._connections
        )

        self._state[
            "broadcast_count"
        ] += 1

        self._state[
            "messages_sent"
        ] += sent

        self._state[
            "send_errors"
        ] += errors

        self._state[
            "last_broadcast_time"
        ] = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        return {
            "broadcasted": True,
            "connections_targeted": targeted,
            "messages_sent": sent,
            "send_errors": errors,
        }

    def get_connection_count(
        self,
    ) -> int:

        return len(
            self._connections
        )

    def get_state(
        self,
    ) -> dict[str, object]:

        return deepcopy(
            self._state
        )
