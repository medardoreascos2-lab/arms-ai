from dataclasses import dataclass
from typing import Any, Callable

from backend.backtesting.walk_forward_splitter import (
    WalkForwardSplitter,
    WalkForwardWindow,
)


@dataclass(frozen=True)
class WalkForwardWindowResult:
    window_number: int
    training_start: int
    training_end: int
    testing_start: int
    testing_end: int
    result: Any


@dataclass
class WalkForwardResult:
    windows: list[WalkForwardWindowResult]

    @property
    def total_windows(self) -> int:
        return len(self.windows)


class WalkForwardEngine:
    """
    Ejecuta una evaluación walk-forward sobre ventanas
    de entrenamiento y prueba.
    """

    def __init__(
        self,
        splitter: WalkForwardSplitter,
        engine_factory: Callable[
            [WalkForwardWindow],
            Any,
        ],
    ) -> None:
        if not callable(engine_factory):
            raise TypeError(
                "engine_factory debe ser callable."
            )

        self.splitter = splitter
        self.engine_factory = engine_factory

    def run(
        self,
        candles: list[Any],
    ) -> WalkForwardResult:
        if not candles:
            raise ValueError(
                "WalkForwardEngine requiere candles."
            )

        windows = self.splitter.split(
            total_items=len(candles),
        )

        results: list[WalkForwardWindowResult] = []

        for window_number, window in enumerate(
            windows,
            start=1,
        ):
            training_candles = candles[
                window.training_start:
                window.training_end
            ]

            testing_candles = candles[
                window.testing_start:
                window.testing_end
            ]

            engine = self.engine_factory(window)

            result = engine.run_walk_forward_window(
                training_candles=training_candles,
                testing_candles=testing_candles,
            )

            results.append(
                WalkForwardWindowResult(
                    window_number=window_number,
                    training_start=window.training_start,
                    training_end=window.training_end,
                    testing_start=window.testing_start,
                    testing_end=window.testing_end,
                    result=result,
                )
            )

        return WalkForwardResult(
            windows=results,
        )
