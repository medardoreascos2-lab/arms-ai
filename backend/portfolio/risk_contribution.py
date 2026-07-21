from __future__ import annotations

from math import sqrt

import numpy as np


class RiskContribution:
    """
    Calcula la contribución de cada activo
    a la volatilidad total del portafolio.
    """

    def calculate(
        self,
        *,
        covariance_matrix: np.ndarray,
        weights: dict[str, float],
    ) -> dict[str, object]:
        if not weights:
            raise ValueError(
                "weights no puede estar vacío."
            )

        assets = tuple(weights)

        normalized_weights = {
            asset: float(weights[asset])
            for asset in assets
        }

        weight_sum = sum(
            normalized_weights.values()
        )

        if abs(weight_sum - 1.0) > 1e-9:
            raise ValueError(
                "weights debe sumar 1.0."
            )

        covariance = np.asarray(
            covariance_matrix,
            dtype=float,
        )

        asset_count = len(assets)

        if covariance.shape != (
            asset_count,
            asset_count,
        ):
            raise ValueError(
                "covariance_matrix debe coincidir "
                "con la cantidad de activos."
            )

        if not np.isfinite(covariance).all():
            raise ValueError(
                "covariance_matrix contiene "
                "valores inválidos."
            )

        weight_vector = np.asarray(
            [
                normalized_weights[asset]
                for asset in assets
            ],
            dtype=float,
        )

        portfolio_variance = float(
            weight_vector
            @ covariance
            @ weight_vector
        )

        if portfolio_variance <= 0.0:
            raise ValueError(
                "portfolio debe tener riesgo positivo."
            )

        portfolio_volatility = sqrt(
            portfolio_variance
        )

        covariance_times_weights = (
            covariance
            @ weight_vector
        )

        marginal_vector = (
            covariance_times_weights
            / portfolio_volatility
        )

        absolute_vector = (
            weight_vector
            * marginal_vector
        )

        percentage_vector = (
            absolute_vector
            / portfolio_volatility
        )

        marginal_contributions = {
            asset: float(
                marginal_vector[index]
            )
            for index, asset
            in enumerate(assets)
        }

        absolute_contributions = {
            asset: float(
                absolute_vector[index]
            )
            for index, asset
            in enumerate(assets)
        }

        percentage_contributions = {
            asset: float(
                percentage_vector[index]
            )
            for index, asset
            in enumerate(assets)
        }

        highest_risk_asset = max(
            percentage_contributions,
            key=percentage_contributions.get,
        )

        lowest_risk_asset = min(
            percentage_contributions,
            key=percentage_contributions.get,
        )

        return {
            "portfolio_volatility": float(
                portfolio_volatility
            ),
            "marginal_contributions": (
                marginal_contributions
            ),
            "absolute_contributions": (
                absolute_contributions
            ),
            "percentage_contributions": (
                percentage_contributions
            ),
            "highest_risk_asset": (
                highest_risk_asset
            ),
            "lowest_risk_asset": (
                lowest_risk_asset
            ),
        }
