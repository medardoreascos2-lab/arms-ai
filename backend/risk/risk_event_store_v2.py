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

    def query_events(
        self,
        *,
        symbol: str | None = None,
        event_type: str | None = None,
        start_timestamp: str | None = None,
        end_timestamp: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not isinstance(
            offset,
            int,
        ) or isinstance(
            offset,
            bool,
        ) or offset < 0:
            raise ValueError(
                "offset no puede ser negativo."
            )

        if limit is not None:
            if not isinstance(
                limit,
                int,
            ) or isinstance(
                limit,
                bool,
            ) or limit <= 0:
                raise ValueError(
                    "limit debe ser mayor que cero."
                )

        normalized_symbol = None

        if symbol is not None:
            normalized_symbol = (
                str(symbol)
                .strip()
                .upper()
            )

            if not normalized_symbol:
                raise ValueError(
                    "symbol no puede estar vacío."
                )

        normalized_event_type = None

        if event_type is not None:
            normalized_event_type = (
                str(event_type)
                .strip()
                .upper()
            )

            if not normalized_event_type:
                raise ValueError(
                    "event_type no puede estar vacío."
                )

        def validate_timestamp_filter(
            value: str | None,
            name: str,
        ) -> None:
            if value is None:
                return

            from datetime import datetime

            candidate = str(value).strip()

            if not candidate:
                raise ValueError(
                    f"{name} no puede estar vacío."
                )

            normalized = candidate

            if normalized.endswith("Z"):
                normalized = (
                    normalized[:-1]
                    + "+00:00"
                )

            try:
                datetime.fromisoformat(
                    normalized
                )
            except ValueError as exc:
                raise ValueError(
                    f"{name} debe ser un timestamp ISO 8601 válido."
                ) from exc

        validate_timestamp_filter(
            start_timestamp,
            "start_timestamp",
        )
        validate_timestamp_filter(
            end_timestamp,
            "end_timestamp",
        )

        events = self.get_events()

        filtered: list[
            dict[str, Any]
        ] = []

        for event in events:
            if normalized_symbol is not None:
                event_symbol = (
                    str(
                        event.get(
                            "symbol",
                            "",
                        )
                    )
                    .strip()
                    .upper()
                )

                if (
                    event_symbol
                    != normalized_symbol
                ):
                    continue

            if normalized_event_type is not None:
                current_event_type = (
                    str(
                        event.get(
                            "event_type",
                            "",
                        )
                    )
                    .strip()
                    .upper()
                )

                if (
                    current_event_type
                    != normalized_event_type
                ):
                    continue

            timestamp = str(
                event.get(
                    "timestamp",
                    "",
                )
            )

            if (
                start_timestamp is not None
                and timestamp < start_timestamp
            ):
                continue

            if (
                end_timestamp is not None
                and timestamp > end_timestamp
            ):
                continue

            filtered.append(
                event
            )

        if limit is None:
            return filtered[offset:]

        if offset == 0:
            return filtered[-limit:]

        return filtered[
            offset:
            offset + limit
        ]

    def clear(
        self,
    ) -> None:
        self._events.clear()
        self._persist()
