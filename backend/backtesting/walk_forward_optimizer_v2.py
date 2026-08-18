from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


class WalkForwardOptimizerV2:
    """
    Orquesta la optimización en training y la validación
    out-of-sample en testing para cada ventana walk-forward.
    """

    REQUIRED_DATASET_KEYS = (
        "window_index",
        "training_start",
        "training_end",
        "testing_start",
        "testing_end",
        "training_items",
        "testing_items",
    )

    def __init__(
        self,
        *,
        training_optimizer,
        candidate_factory,
        testing_evaluator,
        continue_on_error: bool = True,
    ) -> None:

        if not callable(
            getattr(
                training_optimizer,
                "optimize",
                None,
            )
        ):
            raise TypeError(
                "training_optimizer debe implementar optimize()."
            )

        if not callable(
            getattr(
                candidate_factory,
                "build",
                None,
            )
        ):
            raise TypeError(
                "candidate_factory debe implementar build()."
            )

        if not callable(
            getattr(
                testing_evaluator,
                "evaluate",
                None,
            )
        ):
            raise TypeError(
                "testing_evaluator debe implementar evaluate()."
            )

        if not isinstance(
            continue_on_error,
            bool,
        ):
            raise TypeError(
                "continue_on_error debe ser bool."
            )

        self.training_optimizer = (
            training_optimizer
        )

        self.candidate_factory = (
            candidate_factory
        )

        self.testing_evaluator = (
            testing_evaluator
        )

        self.continue_on_error = (
            continue_on_error
        )

    def optimize(
        self,
        *,
        datasets,
        parameter_sets,
        output_directory,
    ) -> WalkForwardOptimizationResultV2:

        normalized_datasets = (
            self._normalize_collection(
                value=datasets,
                field_name="datasets",
            )
        )

        normalized_parameter_sets = (
            self._normalize_collection(
                value=parameter_sets,
                field_name="parameter_sets",
            )
        )

        if not normalized_parameter_sets:
            raise ValueError(
                "parameter_sets no puede estar vacío."
            )

        for parameter_set in (
            normalized_parameter_sets
        ):
            if not isinstance(
                parameter_set,
                dict,
            ):
                raise TypeError(
                    "Cada parameter_set debe ser un dict."
                )

        normalized_output_directory = Path(
            output_directory
        )

        window_results: list[
            dict[str, Any]
        ] = []

        for raw_dataset in normalized_datasets:

            dataset = self._validate_dataset(
                raw_dataset
            )

            window_index = dataset[
                "window_index"
            ]

            window_output_directory = (
                normalized_output_directory
                / f"window_{window_index}"
            )

            training_output_directory = (
                window_output_directory
                / "training"
            )

            testing_output_directory = (
                window_output_directory
                / "testing"
            )

            try:
                candidates = (
                    self.candidate_factory.build(
                        parameter_sets=deepcopy(
                            normalized_parameter_sets
                        ),
                    )
                )

                training_result = (
                    self.training_optimizer.optimize(
                        candidates=candidates,
                        candles=deepcopy(
                            dataset["training_items"]
                        ),
                        output_directory=(
                            window_output_directory
                        ),
                    )
                )

                best_strategy_method = getattr(
                    training_result,
                    "best_strategy",
                    None,
                )

                if not callable(
                    best_strategy_method
                ):
                    raise TypeError(
                        "El resultado de training debe "
                        "implementar best_strategy()."
                    )

                best_training_strategy = (
                    best_strategy_method()
                )

                if not isinstance(
                    best_training_strategy,
                    dict,
                ):
                    raise TypeError(
                        "best_strategy() debe devolver un dict."
                    )

                best_parameters = (
                    best_training_strategy.get(
                        "parameters"
                    )
                )

                if not isinstance(
                    best_parameters,
                    dict,
                ):
                    raise TypeError(
                        "La mejor estrategia debe contener "
                        "parameters como dict."
                    )

                testing_result = (
                    self.testing_evaluator.evaluate(
                        testing_items=deepcopy(
                            dataset["testing_items"]
                        ),
                        parameters=deepcopy(
                            best_parameters
                        ),
                        output_directory=(
                            testing_output_directory
                        ),
                    )
                )

                if not isinstance(
                    testing_result,
                    dict,
                ):
                    raise TypeError(
                        "testing_evaluator.evaluate() "
                        "debe devolver un dict."
                    )

                window_results.append(
                    {
                        "window_index": window_index,
                        "success": True,
                        "training_start": (
                            dataset["training_start"]
                        ),
                        "training_end": (
                            dataset["training_end"]
                        ),
                        "testing_start": (
                            dataset["testing_start"]
                        ),
                        "testing_end": (
                            dataset["testing_end"]
                        ),
                        "training_score": float(
                            best_training_strategy.get(
                                "score",
                                0.0,
                            )
                        ),
                        "testing_score": float(
                            testing_result.get(
                                "score",
                                0.0,
                            )
                        ),
                        "testing_net_pnl": float(
                            testing_result.get(
                                "net_pnl",
                                0.0,
                            )
                        ),
                        "testing_win_rate": float(
                            testing_result.get(
                                "win_rate",
                                0.0,
                            )
                        ),
                        "testing_maximum_drawdown": float(
                            testing_result.get(
                                "maximum_drawdown",
                                0.0,
                            )
                        ),
                        "best_parameters": deepcopy(
                            best_parameters
                        ),
                        "best_training_strategy": deepcopy(
                            best_training_strategy
                        ),
                    }
                )

            except Exception as exc:

                if not self.continue_on_error:
                    raise

                window_results.append(
                    {
                        "window_index": window_index,
                        "success": False,
                        "training_start": (
                            dataset["training_start"]
                        ),
                        "training_end": (
                            dataset["training_end"]
                        ),
                        "testing_start": (
                            dataset["testing_start"]
                        ),
                        "testing_end": (
                            dataset["testing_end"]
                        ),
                        "error": {
                            "type": type(
                                exc
                            ).__name__,
                            "message": str(
                                exc
                            ),
                        },
                    }
                )

        return WalkForwardOptimizationResultV2(
            window_results=window_results,
        )

    @staticmethod
    def _normalize_collection(
        *,
        value,
        field_name: str,
    ) -> list[Any]:

        if isinstance(
            value,
            (
                str,
                bytes,
                dict,
            ),
        ):
            raise TypeError(
                f"{field_name} debe ser una colección."
            )

        try:
            return list(
                value
            )
        except TypeError as exc:
            raise TypeError(
                f"{field_name} debe ser una colección."
            ) from exc

    @classmethod
    def _validate_dataset(
        cls,
        raw_dataset,
    ) -> dict[str, Any]:

        if not isinstance(
            raw_dataset,
            dict,
        ):
            raise TypeError(
                "Cada dataset debe ser un dict."
            )

        for key in cls.REQUIRED_DATASET_KEYS:
            if key not in raw_dataset:
                raise ValueError(
                    f"Falta la clave requerida: {key}."
                )

        dataset = deepcopy(
            raw_dataset
        )

        for key in (
            "window_index",
            "training_start",
            "training_end",
            "testing_start",
            "testing_end",
        ):
            if not isinstance(
                dataset[key],
                int,
            ):
                raise TypeError(
                    f"{key} debe ser int."
                )

        if not isinstance(
            dataset["training_items"],
            list,
        ):
            raise TypeError(
                "training_items debe ser una lista."
            )

        if not isinstance(
            dataset["testing_items"],
            list,
        ):
            raise TypeError(
                "testing_items debe ser una lista."
            )

        return dataset
