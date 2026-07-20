from __future__ import annotations

from math import sqrt

import numpy as np


class EfficientFrontier:
    """
    Genera portafolios aleatorios para aproximar
    la frontera eficiente.
    """

    @staticmethod
    def generate(
        *,
        covariance_matrix: np.ndarray,
        expected_returns: dict[str, float],
        portfolios: int = 1000,
        seed: int | None = None,
    ) -> list[dict[str, object]]:
        if portfolios <= 0:
            raise ValueError(
                "portfolios debe ser mayor que cero."
            )

        assets = tuple(
            expected_returns
        )

        if not assets:
            raise ValueError(
                "expected_returns no puede estar vacío."
            )

        covariance = np.asarray(
            covariance_matrix,
            dtype=float,
        )

        asset_count = len(
            assets
        )

        if covariance.shape != (
            asset_count,
            asset_count,
        ):
            raise ValueError(
                "covariance_matrix debe coincidir "
                "con la cantidad de activos."
            )

        expected_vector = np.array(
            [
                float(
                    expected_returns[asset]
                )
                for asset in assets
            ],
            dtype=float,
        )

        random = np.random.default_rng(
            seed
        )

        results: list[
            dict[str, object]
        ] = []

        for _ in range(portfolios):
            raw_weights = random.random(
                asset_count
            )

            weights = (
                raw_weights
                / raw_weights.sum()
            )

            portfolio_return = float(
                weights @ expected_vector
            )

            portfolio_variance = float(
                weights
                @ covariance
                @ weights
            )

            portfolio_volatility = sqrt(
                max(
                    portfolio_variance,
                    0.0,
                )
            )

            results.append(
                {
                    "expected_return": (
                        portfolio_return
                    ),
                    "volatility": (
                        portfolio_volatility
                    ),
                    "weights": {
                        asset: float(
                            weights[index]
                        )
                        for index, asset
                        in enumerate(assets)
                    },
                }
            )

        return results
