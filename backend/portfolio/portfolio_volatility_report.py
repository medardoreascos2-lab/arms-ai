from dataclasses import dataclass
from math import sqrt
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_correlation_matrix import (
    PortfolioCorrelationMatrix,
)


@dataclass(frozen=True)
class PortfolioVolatilityReport:
    """
    Calcula la volatilidad total y anualizada
    de un portafolio.
    """

    portfolio_volatility: float
    annualized_volatility: float
    asset_volatilities: Mapping[str, float]
    most_volatile_asset: str
    least_volatile_asset: str
    periods_per_year: int

    @classmethod
    def from_inputs(
        cls,
        *,
        weights: dict[str, float],
        volatilities: dict[str, float],
        correlation_matrix: PortfolioCorrelationMatrix,
        periods_per_year: int = 1,
    ) -> "PortfolioVolatilityReport":
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

        if periods_per_year <= 0:
            raise ValueError(
                "periods_per_year debe ser mayor que cero."
            )

        normalized_weights = {
            symbol.strip().upper(): float(value)
            for symbol, value in weights.items()
        }

        normalized_volatilities = {
            symbol.strip().upper(): float(value)
            for symbol, value in volatilities.items()
        }

        weight_assets = set(
            normalized_weights
        )
        volatility_assets = set(
            normalized_volatilities
        )
        matrix_assets = set(
            correlation_matrix.assets
        )

        if weight_assets != volatility_assets:
            raise ValueError(
                "weights y volatilities deben contener "
                "los mismos activos."
            )

        if not weight_assets.issubset(
            matrix_assets
        ):
            raise ValueError(
                "Los activos deben existir en "
                "correlation_matrix."
            )

        for volatility in normalized_volatilities.values():
            if volatility < 0:
                raise ValueError(
                    "Las volatilidades no pueden ser negativas."
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

        portfolio_variance = 0.0

        for first_asset in assets:
            for second_asset in assets:
                covariance = (
                    normalized_volatilities[first_asset]
                    * normalized_volatilities[second_asset]
                    * correlation_matrix.correlation(
                        first_asset,
                        second_asset,
                    )
                )

                portfolio_variance += (
                    decimal_weights[first_asset]
                    * decimal_weights[second_asset]
                    * covariance
                )

        portfolio_variance = max(
            portfolio_variance,
            0.0,
        )

        portfolio_volatility = sqrt(
            portfolio_variance
        )

        annualized_volatility = (
            portfolio_volatility
            * sqrt(periods_per_year)
        )

        most_volatile_asset = max(
            normalized_volatilities,
            key=normalized_volatilities.get,
        )

        least_volatile_asset = min(
            normalized_volatilities,
            key=normalized_volatilities.get,
        )

        return cls(
            portfolio_volatility=round(
                portfolio_volatility,
                6,
            ),
            annualized_volatility=round(
                annualized_volatility,
                6,
            ),
            asset_volatilities=MappingProxyType(
                dict(normalized_volatilities)
            ),
            most_volatile_asset=most_volatile_asset,
            least_volatile_asset=least_volatile_asset,
            periods_per_year=int(
                periods_per_year
            ),
        )
