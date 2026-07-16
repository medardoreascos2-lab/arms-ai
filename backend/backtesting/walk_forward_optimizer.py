from dataclasses import dataclass
from typing import Any

from backend.backtesting.parameter_evaluator import (
    ParameterEvaluation,
)


@dataclass(frozen=True)
class WalkForwardOptimizationResult:
    selected_parameters: dict[str, Any]
    training_evaluation: ParameterEvaluation
    testing_evaluation: ParameterEvaluation
    training_evaluations: list[ParameterEvaluation]


class WalkForwardOptimizer:
    """
    Evalúa todas las combinaciones en entrenamiento,
    selecciona la mejor y la valida fuera de muestra.
    """

    def __init__(
        self,
        parameter_grid: Any,
        evaluator: Any,
        selector: Any,
    ) -> None:
        if parameter_grid is None:
            raise TypeError(
                "parameter_grid es obligatorio."
            )

        if evaluator is None:
            raise TypeError(
                "evaluator es obligatorio."
            )

        if selector is None:
            raise TypeError(
                "selector es obligatorio."
            )

        self.parameter_grid = parameter_grid
        self.evaluator = evaluator
        self.selector = selector

    def optimize(
        self,
        training_candles: list[Any],
        testing_candles: list[Any],
    ) -> WalkForwardOptimizationResult:
        if not training_candles:
            raise ValueError(
                "training_candles no puede estar vacío."
            )

        if not testing_candles:
            raise ValueError(
                "testing_candles no puede estar vacío."
            )

        combinations = self.parameter_grid.generate()

        if not combinations:
            raise ValueError(
                "No existen combinaciones de parámetros."
            )

        training_evaluations = [
            self.evaluator.evaluate(
                parameters=parameters,
                candles=training_candles,
            )
            for parameters in combinations
        ]

        selected_evaluation = self.selector.select(
            candidates=training_evaluations,
        )

        selected_parameters = dict(
            selected_evaluation.parameters
        )

        testing_evaluation = self.evaluator.evaluate(
            parameters=selected_parameters,
            candles=testing_candles,
        )

        return WalkForwardOptimizationResult(
            selected_parameters=selected_parameters,
            training_evaluation=selected_evaluation,
            testing_evaluation=testing_evaluation,
            training_evaluations=training_evaluations,
        )
