from typing import Any, Callable

from backend.backtesting.walk_forward_optimization_report import (
    WalkForwardOptimizationReport,
)
from backend.backtesting.walk_forward_splitter import (
    WalkForwardSplitter,
)


class WalkForwardOptimizationRunner:
    """
    Ejecuta una optimización walk-forward sobre todas
    las ventanas producidas por WalkForwardSplitter.
    """

    def __init__(
        self,
        splitter: WalkForwardSplitter,
        optimizer: Any,
        report_factory: Callable[
            [list[Any]],
            WalkForwardOptimizationReport,
        ] | None = None,
    ) -> None:
        if splitter is None:
            raise TypeError(
                "splitter es obligatorio."
            )

        if optimizer is None:
            raise TypeError(
                "optimizer es obligatorio."
            )

        if report_factory is not None and not callable(
            report_factory
        ):
            raise TypeError(
                "report_factory debe ser callable."
            )

        self.splitter = splitter
        self.optimizer = optimizer
        self.report_factory = (
            report_factory
            or WalkForwardOptimizationReport.from_results
        )

    def run(
        self,
        candles: list[Any],
    ) -> WalkForwardOptimizationReport:
        if not candles:
            raise ValueError(
                "WalkForwardOptimizationRunner requiere candles."
            )

        windows = self.splitter.split(
            total_items=len(candles),
        )

        optimization_results = []

        for window in windows:
            training_candles = candles[
                window.training_start:
                window.training_end
            ]

            testing_candles = candles[
                window.testing_start:
                window.testing_end
            ]

            result = self.optimizer.optimize(
                training_candles=training_candles,
                testing_candles=testing_candles,
            )

            optimization_results.append(result)

        return self.report_factory(
            optimization_results
        )
