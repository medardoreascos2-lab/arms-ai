from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class PortfolioCorrelationMatrix:
    """
    Matriz de correlación de Pearson entre activos.
    """

    assets: tuple[str, ...]
    matrix: Mapping[str, Mapping[str, float]]

    @classmethod
    def from_returns(
        cls,
        returns: dict[
            str,
            list[float] | tuple[float, ...],
        ],
    ) -> "PortfolioCorrelationMatrix":
        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        assets = tuple(
            symbol.strip().upper()
            for symbol in returns
        )

        normalized = {
            symbol.strip().upper(): tuple(
                float(value)
                for value in values
            )
            for symbol, values in returns.items()
        }

        lengths = {
            len(values)
            for values in normalized.values()
        }

        if len(lengths) != 1:
            raise ValueError(
                "Todas las series deben tener la misma length."
            )

        sample_size = next(iter(lengths))

        if sample_size < 2:
            raise ValueError(
                "Cada serie requiere al menos 2 valores."
            )

        matrix: dict[
            str,
            Mapping[str, float],
        ] = {}

        for first_asset in assets:
            row: dict[str, float] = {}

            for second_asset in assets:
                if first_asset == second_asset:
                    correlation = 1.0
                else:
                    correlation = cls._pearson(
                        normalized[first_asset],
                        normalized[second_asset],
                    )

                row[second_asset] = round(
                    correlation,
                    6,
                )

            matrix[first_asset] = MappingProxyType(
                row
            )

        return cls(
            assets=assets,
            matrix=MappingProxyType(
                matrix
            ),
        )

    @staticmethod
    def _pearson(
        first: tuple[float, ...],
        second: tuple[float, ...],
    ) -> float:
        first_mean = (
            sum(first)
            / len(first)
        )
        second_mean = (
            sum(second)
            / len(second)
        )

        covariance = sum(
            (
                first_value - first_mean
            )
            * (
                second_value - second_mean
            )
            for first_value, second_value in zip(
                first,
                second,
            )
        )

        first_variance = sum(
            (
                value - first_mean
            ) ** 2
            for value in first
        )
        second_variance = sum(
            (
                value - second_mean
            ) ** 2
            for value in second
        )

        denominator = sqrt(
            first_variance
            * second_variance
        )

        if denominator == 0:
            return 0.0

        return covariance / denominator

    def correlation(
        self,
        first_asset: str,
        second_asset: str,
    ) -> float:
        first = first_asset.strip().upper()
        second = second_asset.strip().upper()

        try:
            return self.matrix[first][second]
        except KeyError as error:
            raise KeyError(
                f"Activo no encontrado: "
                f"{first_asset} o {second_asset}"
            ) from error
