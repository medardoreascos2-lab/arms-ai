from __future__ import annotations

from copy import deepcopy
from typing import Any


class SignalHistoryStore:
    """
    Almacena el historial de señales por
    símbolo y temporalidad.
    """

    def __init__(
        self,
        *,
        max_signals: int = 500,
    ) -> None:
        if max_signals <= 0:
            raise ValueError(
                "max_signals debe ser mayor que cero."
            )

        self.max_signals = max_signals

        self._history: dict[
            tuple[str, str],
            list[dict[str, Any]],
        ] = {}

    def append(
        self,
        signal: dict[str, Any],
    ) -> None:
        symbol = str(
            signal["symbol"]
        ).strip().upper()

        timeframe = str(
            signal["timeframe"]
        ).strip().lower()

        key = (
            symbol,
            timeframe,
        )

        history = self._history.setdefault(
            key,
            [],
        )

        generated_at = signal[
            "generated_at"
        ]

        history[:] = [
            existing
            for existing in history
            if existing["generated_at"]
            != generated_at
        ]

        history.append(
            deepcopy(signal)
        )

        history.sort(
            key=lambda item: item[
                "generated_at"
            ]
        )

        if len(history) > self.max_signals:
            del history[
                : len(history)
                - self.max_signals
            ]

    def get_history(
        self,
        *,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            raise ValueError(
                "limit debe ser mayor que cero."
            )

        key = (
            str(symbol).strip().upper(),
            str(timeframe).strip().lower(),
        )

        history = self._history.get(
            key,
            [],
        )

        return deepcopy(
            history[-limit:]
        )
