from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)


@dataclass(frozen=True)
class PortfolioRiskParityOptimizer:
    """
    Construye un portafolio long-only usando pesos
    inversamente proporcionales a la volatilidad.
    """

    assets: tuple[str, ...]
    weights: Mapping[str, float]
    risk_contributions: Mapping[str, float]
    portfolio_variance: float
    portfolio_volatility: float

    @classmethod
    def optimize(
        cls,
        *,
        covariance_matrix: PortfolioCovarianceMatrix,
    ) -> "PortfolioRiskParityOptimizer":
        if not isinstance(
            covariance_matrix,
            PortfolioCovarianceMatrix,
        ):
            raise TypeError(
                "covariance_matrix debe ser "
                "PortfolioCovarianceMatrix."
            )

        assets = covariance_matrix.assets

        inverse_volatilities: dict[str, float] = {}

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

            volatility = sqrt(
                variance
            )

            inverse_volatilities[asset] = (
                1.0
                / volatility
            )

        normalization = sum(
            inverse_volatilities.values()
        )

        raw_weights = {
            asset: (
                inverse_volatilities[asset]
                / normalization
                * 100.0
            )
            for asset in assets
        }

        weights = {
            asset: round(
                value,
                6,
            )
            for asset, value in raw_weights.items()
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

        portfolio_volatility = sqrt(
            portfolio_variance
        )

        marginal_contributions: dict[str, float] = {}

        for asset in assets:
            covariance_with_portfolio = sum(
                covariance_matrix.covariance(
                    asset,
                    other_asset,
                )
                * decimal_weights[other_asset]
                for other_asset in assets
            )

            marginal_contributions[asset] = (
                decimal_weights[asset]
                * covariance_with_portfolio
            )

        total_contribution = sum(
            marginal_contributions.values()
        )

        if total_contribution == 0:
            risk_contributions = {
                asset: 0.0
                for asset in assets
            }
        else:
            risk_contributions = {
                asset: round(
                    marginal_contributions[asset]
                    / total_contribution
                    * 100.0,
                    6,
                )
                for asset in assets
            }

            contribution_difference = round(
                100.0
                - sum(
                    risk_contributions.values()
                ),
                6,
            )

            risk_contributions[assets[0]] = round(
                risk_contributions[assets[0]]
                + contribution_difference,
                6,
            )

        return cls(
            assets=assets,
            weights=MappingProxyType(
                dict(weights)
            ),
            risk_contributions=MappingProxyType(
                dict(risk_contributions)
            ),
            portfolio_variance=round(
                portfolio_variance,
                6,
            ),
            portfolio_volatility=round(
                portfolio_volatility,
                6,
            ),
        )
