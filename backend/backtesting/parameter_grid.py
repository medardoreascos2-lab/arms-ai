from collections.abc import Mapping
from itertools import product
from typing import Any


class ParameterGrid:
    """
    Genera todas las combinaciones posibles de parámetros.
    """

    def __init__(
        self,
        parameters: Mapping[str, list[Any]],
    ) -> None:
        if not isinstance(parameters, Mapping):
            raise TypeError(
                "parameters debe ser un mapping."
            )

        copied_parameters: dict[str, list[Any]] = {}

        for name, values in parameters.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    "Cada parámetro requiere un nombre válido."
                )

            copied_values = list(values)

            if not copied_values:
                raise ValueError(
                    f"El parámetro '{name}' requiere valores."
                )

            copied_parameters[name] = copied_values

        self.parameters = copied_parameters

    def generate(
        self,
    ) -> list[dict[str, Any]]:
        if not self.parameters:
            return [{}]

        names = list(self.parameters.keys())
        value_groups = [
            self.parameters[name]
            for name in names
        ]

        combinations = []

        for values in product(*value_groups):
            combinations.append(
                dict(
                    zip(
                        names,
                        values,
                        strict=True,
                    )
                )
            )

        return combinations
