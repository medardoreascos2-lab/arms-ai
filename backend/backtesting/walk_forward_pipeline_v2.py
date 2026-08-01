from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.backtesting.walk_forward_optimization_result_v2 import (
    WalkForwardOptimizationResultV2,
)


class WalkForwardPipelineV2:
    """
    Orquesta el proceso completo de Walk-Forward:

    1. Generar ventanas
    2. Dividir el dataset
    3. Ejecutar la optimización
    """

    def __init__(
        self,
        *,
        window_generator,
        dataset_splitter,
        walk_forward_optimizer,
    ) -> None:

        if not callable(
            getattr(
                window_generator,
                "generate",
                None,
            )
        ):
            raise TypeError(
                "window_generator debe implementar generate()."
            )

        if not callable(
            getattr(
                dataset_splitter,
                "split",
                None,
            )
        ):
            raise TypeError(
                "dataset_splitter debe implementar split()."
            )

        if not callable(
            getattr(
                walk_forward_optimizer,
                "optimize",
                None,
            )
        ):
            raise TypeError(
                "walk_forward_optimizer debe implementar optimize()."
            )

        self.window_generator = window_generator
        self.dataset_splitter = dataset_splitter
        self.walk_forward_optimizer = (
            walk_forward_optimizer
        )

    def run(
        self,
        *,
        items,
        parameter_sets,
        output_directory,
    ) -> WalkForwardOptimizationResultV2:

        if isinstance(
            items,
            (
                str,
                bytes,
                dict,
            ),
        ) or items is None:
            raise TypeError(
                "items debe ser una colección."
            )

        try:
            normalized_items = list(items)
        except TypeError as exc:
            raise TypeError(
                "items debe ser una colección."
            ) from exc

        parameter_sets = list(
            parameter_sets
        )

        if not parameter_sets:
            raise ValueError(
                "parameter_sets no puede estar vacío."
            )

        output_directory = Path(
            output_directory
        )

        windows = (
            self.window_generator.generate(
                total_items=len(
                    normalized_items
                )
            )
        )

        if not windows:
            return WalkForwardOptimizationResultV2(
                window_results=[]
            )

        datasets = (
            self.dataset_splitter.split(
                items=normalized_items,
                windows=windows,
            )
        )

        return (
            self.walk_forward_optimizer.optimize(
                datasets=datasets,
                parameter_sets=parameter_sets,
                output_directory=output_directory,
            )
        )
