from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_minimum_variance_optimizer import (
    PortfolioMinimumVarianceOptimizer,
)


@dataclass(frozen=True)
class EfficientFrontierPortfolio:
    """
    Representa un punto individual de la frontera.
    """

    weights: Mapping[str, float]
    portfolio_variance: float
    portfolio_volatility: float


@dataclass(frozen=True)
class PortfolioEfficientFrontier:
    """
    Genera una familia determinista de portafolios
    entre mínima varianza y máxima volatilidad.
    """

    assets: tuple[str, ...]
    points: int
    portfolios: tuple[
        EfficientFrontierPortfolio,
        ...,
    ]

    @classmethod
    def generate(
        cls,
        *,
        covariance_matrix: PortfolioCovarianceMatrix,
        points: int,
    ) -> "PortfolioEfficientFrontier":
        if not isinstance(
            covariance_matrix,
            PortfolioCovarianceMatrix,
        ):
            raise TypeError(
                "covariance_matrix debe ser "
                "PortfolioCovarianceMatrix."
            )

        if points <= 0:
            raise ValueError(
                "points debe ser mayor que cero."
            )

        assets = covariance_matrix.assets

        minimum_variance = (
            PortfolioMinimumVarianceOptimizer.optimize(
                covariance_matrix=covariance_matrix,
            )
        )

        highest_volatility_asset = max(
            assets,
            key=lambda asset: (
                covariance_matrix.covariance(
                    asset,
                    asset,
                )
            ),
        )

        frontier_portfolios = []

        for index in range(points):
            if points == 1:
                interpolation = 0.0
            else:
                interpolation = (
                    index
                    / (
                        points - 1
                    )
                )

            weights = {}

            for asset in assets:
                minimum_weight = (
                    minimum_variance.weights[
                        asset
                    ]
                )

                target_weight = (
                    100.0
                    if asset
                    == highest_volatility_asset
                    else 0.0
                )

                weight = (
                    minimum_weight
                    * (
                        1.0
                        - interpolation
                    )
                    + target_weight
                    * interpolation
                )

                weights[asset] = round(
                    weight,
                    6,
                )

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
                        decimal_weights[
                            first_asset
                        ]
                        * decimal_weights[
                            second_asset
                        ]
                        * covariance_matrix.covariance(
                            first_asset,
                            second_asset,
                        )
                    )

            portfolio_variance = max(
                portfolio_variance,
                0.0,
            )

            frontier_portfolios.append(
                EfficientFrontierPortfolio(
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
            )

        return cls(
            assets=assets,
            points=int(points),
            portfolios=tuple(
                frontier_portfolios
            ),
        )
