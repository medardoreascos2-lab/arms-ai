from __future__ import annotations

from copy import deepcopy
from typing import Any


class LiveSignalStore:
    """
    Mantiene la última señal disponible
    por símbolo y temporalidad.
    """

    REQUIRED_FIELDS = (
        "symbol",
        "timeframe",
        "action",
        "approved",
        "score",
        "grade",
        "probability",
        "entry_price",
        "stop_loss",
        "take_profit",
    )

    def __init__(self) -> None:
        self._signals: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

    def save(
        self,
        signal: dict[str, Any],
    ) -> None:
        self._validate_signal(
            signal
        )

        symbol = str(
            signal["symbol"]
        ).strip().upper()

        timeframe = str(
            signal["timeframe"]
        ).strip().lower()

        if not symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if not timeframe:
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        normalized_signal = deepcopy(
            signal
        )

        normalized_signal["symbol"] = (
            symbol
        )

        normalized_signal["timeframe"] = (
            timeframe
        )

        self._signals[
            (symbol, timeframe)
        ] = normalized_signal

    def get_latest(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> dict[str, Any] | None:
        key = (
            str(symbol).strip().upper(),
            str(timeframe).strip().lower(),
        )

        signal = self._signals.get(
            key
        )

        if signal is None:
            return None

        return deepcopy(
            signal
        )

    def clear(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> None:
        if (
            symbol is None
            and timeframe is None
        ):
            self._signals.clear()
            return

        if (
            symbol is None
            or timeframe is None
        ):
            raise ValueError(
                "symbol y timeframe deben proporcionarse juntos."
            )

        key = (
            str(symbol).strip().upper(),
            str(timeframe).strip().lower(),
        )

        self._signals.pop(
            key,
            None,
        )

    def _validate_signal(
        self,
        signal: dict[str, Any],
    ) -> None:
        if not isinstance(
            signal,
            dict,
        ):
            raise TypeError(
                "signal debe ser un diccionario."
            )

        for field in self.REQUIRED_FIELDS:
            if field not in signal:
                raise KeyError(
                    field
                )
