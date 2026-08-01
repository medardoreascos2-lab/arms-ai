from __future__ import annotations

from itertools import product
from typing import Any


class ParameterGridGeneratorV2:
    """
    Genera todas las combinaciones posibles
    de un conjunto de parámetros.
    """

    def generate(
        self,
        parameter_grid,
    ) -> list[dict[str, Any]]:

        if not isinstance(
            parameter_grid,
            dict,
        ):
            raise TypeError(
                "parameter_grid debe ser un dict."
            )

        if not parameter_grid:
            return []

        parameter_names: list[str] = []
        parameter_values: list[list[Any]] = []

        for raw_name, raw_values in (
            parameter_grid.items()
        ):

            normalized_name = str(
                raw_name
            ).strip()

            if not normalized_name:
                raise ValueError(
                    "Los nombres de parámetros "
                    "no pueden estar vacíos."
                )

            if isinstance(
                raw_values,
                (
                    str,
                    bytes,
                    dict,
                ),
            ):
                raise TypeError(
                    f"{normalized_name} debe contener "
                    "una colección de valores."
                )

            try:
                normalized_values = list(
                    raw_values
                )
            except TypeError as exc:
                raise TypeError(
                    f"{normalized_name} debe contener "
                    "una colección de valores."
                ) from exc

            if not normalized_values:
                return []

            parameter_names.append(
                normalized_name
            )

            parameter_values.append(
                normalized_values
            )

        combinations: list[
            dict[str, Any]
        ] = []

        for values in product(
            *parameter_values
        ):
            combinations.append(
                dict(
                    zip(
                        parameter_names,
                        values,
                        strict=True,
                    )
                )
            )

        return combinations
