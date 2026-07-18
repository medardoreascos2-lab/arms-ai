from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)


@dataclass(frozen=True)
class PortfolioCovarianceMatrix:
    """
    Matriz de covarianza construida a partir de
    volatilidades y correlaciones.
    """

    assets: tuple[str, ...]
    matrix: Mapping[str, Mapping[str, float]]
    volatilities: Mapping[str, float]

    @classmethod
    def from_inputs(
        cls,
        *,
        volatilities: dict[str, float],
        correlation_matrix: PortfolioCorrelationMatrix,
    ) -> "PortfolioCovarianceMatrix":
        if not isinstance(
            correlation_matrix,
            PortfolioCorrelationMatrix,
        ):
            raise TypeError(
                "correlation_matrix debe ser "
                "PortfolioCorrelationMatrix."
            )

        if not volatilities:
            raise ValueError(
                "volatilities no puede estar vacío."
            )

        normalized_volatilities = {
            symbol.strip().upper(): float(value)
            for symbol, value in volatilities.items()
        }

        volatility_assets = set(
            normalized_volatilities
        )
        correlation_assets = set(
            correlation_matrix.assets
        )

        if volatility_assets != correlation_assets:
            raise ValueError(
                "volatilities debe contener los mismos "
                "activos que correlation_matrix."
            )

        for volatility in normalized_volatilities.values():
            if volatility < 0:
                raise ValueError(
                    "La volatilidad no puede ser negativa."
                )

        assets = correlation_matrix.assets

        matrix: dict[
            str,
            Mapping[str, float],
        ] = {}

        for first_asset in assets:
            row: dict[str, float] = {}

            for second_asset in assets:
                covariance = (
                    normalized_volatilities[first_asset]
                    * normalized_volatilities[second_asset]
                    * correlation_matrix.correlation(
                        first_asset,
                        second_asset,
                    )
                )

                row[second_asset] = round(
                    covariance,
                    10,
                )

            matrix[first_asset] = MappingProxyType(
                row
            )

        return cls(
            assets=assets,
            matrix=MappingProxyType(
                matrix
            ),
            volatilities=MappingProxyType(
                dict(normalized_volatilities)
            ),
        )

    def covariance(
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
                "Activo no encontrado: "
                f"{first_asset} o {second_asset}"
            ) from error
