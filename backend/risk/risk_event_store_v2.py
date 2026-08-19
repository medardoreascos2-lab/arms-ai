from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


class RiskEventStoreV2:
    """
    Persistent JSON-backed storage for
    execution risk events.

    The store owns its in-memory state and
    persists every mutation to disk.
    """

    def __init__(
        self,
        *,
        path: str | Path,
        max_events: int = 1000,
    ) -> None:
        if not isinstance(
            max_events,
            int,
        ) or isinstance(
            max_events,
            bool,
        ) or max_events <= 0:
            raise ValueError(
                "max_events debe ser mayor que cero."
            )

        self.path = Path(path)
        self.max_events = max_events

        self._events: list[
            dict[str, Any]
        ] = []

        self._load()

    def _load(
        self,
    ) -> None:
        if not self.path.exists():
            self._events = []
            return

        try:
            raw = self.path.read_text(
                encoding="utf-8",
            )

            payload = json.loads(
                raw
            )

        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "No se pudo cargar el almacén "
                "de eventos de riesgo."
            ) from exc

        if not isinstance(
            payload,
            list,
        ):
            raise ValueError(
                "El almacén de eventos de "
                "riesgo debe contener una lista."
            )

        normalized: list[
            dict[str, Any]
        ] = []

        for event in payload:
            if not isinstance(
                event,
                dict,
            ):
                raise ValueError(
                    "Cada evento persistido "
                    "debe ser un diccionario."
                )

            normalized.append(
                deepcopy(event)
            )

        if len(normalized) > self.max_events:
            normalized = normalized[
                -self.max_events:
            ]

        self._events = normalized

    def _persist(
        self,
    ) -> None:
        try:
            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            payload = json.dumps(
                self._events,
                ensure_ascii=False,
                indent=2,
            )

            self.path.write_text(
                payload,
                encoding="utf-8",
            )

        except (
            OSError,
            TypeError,
            ValueError,
        ) as exc:
            raise ValueError(
                "No se pudo persistir el "
                "almacén de eventos de riesgo."
            ) from exc

    def append(
        self,
        event: dict[str, Any],
    ) -> None:
        if not isinstance(
            event,
            dict,
        ):
            raise TypeError(
                "event debe ser un diccionario."
            )

        stored_event = deepcopy(
            event
        )

        self._events.append(
            stored_event
        )

        if len(self._events) > self.max_events:
            del self._events[
                : len(self._events)
                - self.max_events
            ]

        self._persist()

    def get_events(
        self,
    ) -> list[dict[str, Any]]:
        return deepcopy(
            self._events
        )

    def clear(
        self,
    ) -> None:
        self._events.clear()
        self._persist()
