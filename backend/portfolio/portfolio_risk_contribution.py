from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)


@dataclass(frozen=True)
class PortfolioRiskContribution:
    """
    Calcula la contribución porcentual de cada activo
    al riesgo total del portafolio.
    """

    contributions: Mapping[str, float]
    portfolio_volatility: float
    highest_risk_asset: str
    lowest_risk_asset: str

    @classmethod
    def from_inputs(
        cls,
        *,
        weights: dict[str, float],
        volatilities: dict[str, float],
        correlation_matrix: PortfolioCorrelationMatrix,
    ) -> "PortfolioRiskContribution":
        if not weights:
            raise ValueError(
                "weights no puede estar vacío."
            )

        if not volatilities:
            raise ValueError(
                "volatilities no puede estar vacío."
            )

        if not isinstance(
            correlation_matrix,
            PortfolioCorrelationMatrix,
        ):
            raise TypeError(
                "correlation_matrix debe ser "
                "PortfolioCorrelationMatrix."
            )

        normalized_weights = {
            symbol.strip().upper(): float(value)
            for symbol, value in weights.items()
        }

        normalized_volatilities = {
            symbol.strip().upper(): float(value)
            for symbol, value in volatilities.items()
        }

        weight_symbols = set(
            normalized_weights
        )
        volatility_symbols = set(
            normalized_volatilities
        )
        matrix_symbols = set(
            correlation_matrix.assets
        )

        if weight_symbols != volatility_symbols:
            raise ValueError(
                "weights y volatilities deben contener "
                "los mismos activos."
            )

        if not weight_symbols.issubset(
            matrix_symbols
        ):
            raise ValueError(
                "Los activos deben existir en "
                "correlation_matrix."
            )

        total_weight = sum(
            abs(value)
            for value in normalized_weights.values()
        )

        if total_weight == 0:
            raise ValueError(
                "La suma de weights no puede ser cero."
            )

        decimal_weights = {
            symbol: value / total_weight
            for symbol, value in normalized_weights.items()
        }

        assets = tuple(
            decimal_weights
        )

        covariance_matrix: dict[
            str,
            dict[str, float],
        ] = {}

        for first_asset in assets:
            covariance_matrix[first_asset] = {}

            for second_asset in assets:
                covariance_matrix[first_asset][second_asset] = (
                    normalized_volatilities[first_asset]
                    * normalized_volatilities[second_asset]
                    * correlation_matrix.correlation(
                        first_asset,
                        second_asset,
                    )
                )

        portfolio_variance = 0.0

        for first_asset in assets:
            for second_asset in assets:
                portfolio_variance += (
                    decimal_weights[first_asset]
                    * decimal_weights[second_asset]
                    * covariance_matrix[first_asset][second_asset]
                )

        portfolio_variance = max(
            portfolio_variance,
            0.0,
        )

        portfolio_volatility = sqrt(
            portfolio_variance
        )

        if portfolio_volatility == 0:
            contributions = {
                symbol: 0.0
                for symbol in assets
            }
        else:
            marginal_contributions = {}

            for asset in assets:
                covariance_with_portfolio = sum(
                    covariance_matrix[asset][other]
                    * decimal_weights[other]
                    for other in assets
                )

                marginal_contributions[asset] = (
                    decimal_weights[asset]
                    * covariance_with_portfolio
                    / portfolio_volatility
                )

            raw_total = sum(
                marginal_contributions.values()
            )

            if raw_total == 0:
                contributions = {
                    symbol: 0.0
                    for symbol in assets
                }
            else:
                contributions = {
                    symbol: round(
                        value / raw_total * 100,
                        2,
                    )
                    for symbol, value
                    in marginal_contributions.items()
                }

        highest_risk_asset = max(
            contributions,
            key=contributions.get,
        )

        lowest_risk_asset = min(
            contributions,
            key=contributions.get,
        )

        return cls(
            contributions=MappingProxyType(
                dict(contributions)
            ),
            portfolio_volatility=round(
                portfolio_volatility,
                6,
            ),
            highest_risk_asset=highest_risk_asset,
            lowest_risk_asset=lowest_risk_asset,
        )
