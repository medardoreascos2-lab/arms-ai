from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)


@dataclass(frozen=True)
class PortfolioMinimumVarianceOptimizer:
    """
    Calcula un portafolio long-only usando pesos
    inversamente proporcionales a la varianza.
    """

    assets: tuple[str, ...]
    weights: Mapping[str, float]
    portfolio_variance: float
    portfolio_volatility: float

    @classmethod
    def optimize(
        cls,
        *,
        covariance_matrix: PortfolioCovarianceMatrix,
    ) -> "PortfolioMinimumVarianceOptimizer":
        if not isinstance(
            covariance_matrix,
            PortfolioCovarianceMatrix,
        ):
            raise TypeError(
                "covariance_matrix debe ser "
                "PortfolioCovarianceMatrix."
            )

        assets = covariance_matrix.assets

        if len(assets) == 1:
            asset = assets[0]
            variance = covariance_matrix.covariance(
                asset,
                asset,
            )

            return cls(
                assets=assets,
                weights=MappingProxyType(
                    {
                        asset: 100.0,
                    }
                ),
                portfolio_variance=round(
                    variance,
                    6,
                ),
                portfolio_volatility=round(
                    sqrt(
                        max(
                            variance,
                            0.0,
                        )
                    ),
                    6,
                ),
            )

        inverse_variances: dict[str, float] = {}

        for asset in assets:
            variance = covariance_matrix.covariance(
                asset,
                asset,
            )

            if variance <= 0:
                raise ValueError(
                    "La varianza de cada activo "
                    "debe ser mayor que cero."
                )

            inverse_variances[asset] = (
                1.0
                / variance
            )

        normalization = sum(
            inverse_variances.values()
        )

        raw_weights = {
            asset: (
                inverse_variances[asset]
                / normalization
                * 100.0
            )
            for asset in assets
        }

        weights = {
            asset: round(
                weight,
                6,
            )
            for asset, weight in raw_weights.items()
        }

        rounding_difference = round(
            100.0
            - sum(
                weights.values()
            ),
            6,
        )

        weights[assets[0]] = round(
            weights[assets[0]]
            + rounding_difference,
            6,
        )

        decimal_weights = {
            asset: (
                weights[asset]
                / 100.0
            )
            for asset in assets
        }

        portfolio_variance = 0.0

        for first_asset in assets:
            for second_asset in assets:
                portfolio_variance += (
                    decimal_weights[first_asset]
                    * decimal_weights[second_asset]
                    * covariance_matrix.covariance(
                        first_asset,
                        second_asset,
                    )
                )

        portfolio_variance = max(
            portfolio_variance,
            0.0,
        )

        return cls(
            assets=assets,
            weights=MappingProxyType(
                dict(weights)
            ),
            portfolio_variance=round(
                portfolio_variance,
                6,
            ),
            portfolio_volatility=round(
                sqrt(
                    portfolio_variance
                ),
                6,
            ),
        )
