from __future__ import annotations

from collections.abc import Iterable

from backend.models.candle import Candle


class ReplayEngineV2:
    """
    Motor determinista para reproducir velas históricas
    una por una.
    """

    def __init__(self) -> None:
        self._candles: list[Candle] = []
        self._position: int = 0

    def load(
        self,
        candles: Iterable[Candle],
    ) -> None:
        loaded_candles = list(candles)

        if not loaded_candles:
            raise ValueError(
                "candles no puede estar vacío."
            )

        for candle in loaded_candles:
            if not isinstance(
                candle,
                Candle,
            ):
                raise TypeError(
                    "Todos los elementos deben ser Candle."
                )

        self._candles = sorted(
            loaded_candles,
            key=lambda candle: candle.timestamp,
        )

        self._position = 0

    def current(self) -> Candle | None:
        if not self._candles:
            return None

        return self._candles[
            self._position
        ]

    def next(self) -> Candle:
        if not self._candles:
            raise RuntimeError(
                "No hay velas cargadas."
            )

        if not self.has_next():
            raise StopIteration(
                "La reproducción llegó al final."
            )

        self._position += 1

        return self._candles[
            self._position
        ]

    def has_next(self) -> bool:
        if not self._candles:
            return False

        return (
            self._position
            < len(self._candles) - 1
        )

    def reset(self) -> None:
        if not self._candles:
            raise RuntimeError(
                "No hay velas cargadas."
            )

        self._position = 0

    def position(self) -> int:
        return self._position

    def total(self) -> int:
        return len(
            self._candles
        )

    def is_finished(self) -> bool:
        if not self._candles:
            return False

        return not self.has_next()
