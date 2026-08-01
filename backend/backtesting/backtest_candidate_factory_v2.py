from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable

from backend.backtesting.backtest_optimizer_v2 import (
    BacktestOptimizationCandidateV2,
)


class BacktestCandidateFactoryV2:
    """
    Convierte conjuntos de parámetros en candidatos
    listos para BacktestOptimizerV2.
    """

    NAME_ALIASES = {
        "ema": "EMA",
        "stop_loss": "SL",
        "take_profit": "TP",
    }

    def __init__(
        self,
        *,
        pipeline_factory: Callable,
    ) -> None:

        if not callable(
            pipeline_factory
        ):
            raise TypeError(
                "pipeline_factory debe ser callable."
            )

        self.pipeline_factory = (
            pipeline_factory
        )

    def build(
        self,
        *,
        parameter_sets,
    ) -> list[
        BacktestOptimizationCandidateV2
    ]:

        if isinstance(
            parameter_sets,
            (
                str,
                bytes,
                dict,
            ),
        ):
            raise TypeError(
                "parameter_sets debe ser una colección."
            )

        try:
            normalized_parameter_sets = list(
                parameter_sets
            )
        except TypeError as exc:
            raise TypeError(
                "parameter_sets debe ser una colección."
            ) from exc

        candidates: list[
            BacktestOptimizationCandidateV2
        ] = []

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

            normalized_parameters = deepcopy(
                parameter_set
            )

            name = self._build_name(
                normalized_parameters
            )

            pipeline = self.pipeline_factory(
                deepcopy(
                    normalized_parameters
                )
            )

            candidate = (
                BacktestOptimizationCandidateV2(
                    name=name,
                    pipeline=pipeline,
                    json_filename=(
                        f"{name}.json"
                    ),
                    html_filename=(
                        f"{name}.html"
                    ),
                    parameters=(
                        normalized_parameters
                    ),
                )
            )

            candidates.append(
                candidate
            )

        return candidates

    @classmethod
    def _build_name(
        cls,
        parameters: dict[str, Any],
    ) -> str:

        if not parameters:
            raise ValueError(
                "parameter_set no puede estar vacío."
            )

        parts: list[str] = []

        for key, value in (
            parameters.items()
        ):
            normalized_key = str(
                key
            ).strip()

            if not normalized_key:
                raise ValueError(
                    "Los nombres de parámetros "
                    "no pueden estar vacíos."
                )

            label = cls.NAME_ALIASES.get(
                normalized_key,
                normalized_key.upper(),
            )

            normalized_value = str(
                value
            ).strip()

            parts.append(
                f"{label}{normalized_value}"
            )

        return "_".join(
            parts
        )
