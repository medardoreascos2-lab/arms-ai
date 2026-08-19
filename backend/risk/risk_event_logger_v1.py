from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


class RiskEventLoggerV1:
    """
    Registro de eventos de riesgo
    de ARMS AI.

    Puede operar en dos modos:

    - memoria local legacy;
    - store persistente inyectado.

    El modo legacy se conserva para
    compatibilidad con consumidores V1.
    """

    def __init__(
        self,
        store: Any | None = None,
    ) -> None:

        self.store = store
        self.events: list[dict[str, Any]] = []

    def log_event(
        self,
        event: dict,
    ) -> dict[str, Any]:

        record = {
            "timestamp":
                datetime.now(timezone.utc)
                .isoformat(),
            **deepcopy(event),
        }

        if self.store is not None:
            stored_record = deepcopy(record)

            self.store.append(
                stored_record
            )

            return deepcopy(record)

        self.events.append(
            deepcopy(record)
        )

        return deepcopy(record)

    def get_events(
        self,
    ) -> list[dict[str, Any]]:

        if self.store is not None:
            return deepcopy(
                self.store.get_events()
            )

        return deepcopy(
            self.events
        )
