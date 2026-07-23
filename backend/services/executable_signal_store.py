from __future__ import annotations

from copy import deepcopy
from typing import Any


class ExecutableSignalStore:
    """
    Mantiene la última señal oficial aceptada
    por símbolo y temporalidad.
    """

    REQUIRED_FIELDS = (
        "symbol",
        "timeframe",
        "action",
        "accepted",
        "status",
        "generated_at",
    )

    def __init__(self) -> None:
        self._signals: dict[
            tuple[str, str],
            dict[str, Any],
        ] = {}

    def save(
        self,
        execution: dict[str, Any],
    ) -> None:
        self._validate_execution(
            execution
        )

        if not bool(
            execution["accepted"]
        ):
            raise ValueError(
                "accepted debe ser True."
            )

        if (
            str(
                execution["status"]
            ).strip().upper()
            != "ACCEPTED"
        ):
            raise ValueError(
                "status debe ser ACCEPTED."
            )

        symbol = str(
            execution["symbol"]
        ).strip().upper()

        timeframe = str(
            execution["timeframe"]
        ).strip().lower()

        if not symbol:
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if not timeframe:
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        normalized = deepcopy(
            execution
        )

        normalized["symbol"] = symbol
        normalized["timeframe"] = timeframe
        normalized["status"] = "ACCEPTED"
        normalized["accepted"] = True

        self._signals[
            (symbol, timeframe)
        ] = normalized

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

        execution = self._signals.get(
            key
        )

        if execution is None:
            return None

        return deepcopy(
            execution
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

    def _validate_execution(
        self,
        execution: dict[str, Any],
    ) -> None:
        if not isinstance(
            execution,
            dict,
        ):
            raise TypeError(
                "execution debe ser un diccionario."
            )

        for field in self.REQUIRED_FIELDS:
            if field not in execution:
                raise KeyError(
                    field
                )
