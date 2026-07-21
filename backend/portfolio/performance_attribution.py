from __future__ import annotations


class PerformanceAttribution:
    """
    Calcula una atribución de desempeño por activo.
    """

    def calculate(
        self,
        *,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> dict[str, object]:
        if (
            not portfolio_weights
            or not benchmark_weights
        ):
            raise ValueError(
                "weights no puede estar vacío."
            )

        portfolio_weight_sum = sum(
            float(value)
            for value in portfolio_weights.values()
        )

        benchmark_weight_sum = sum(
            float(value)
            for value in benchmark_weights.values()
        )

        if (
            abs(portfolio_weight_sum - 1.0) > 1e-9
            or abs(benchmark_weight_sum - 1.0) > 1e-9
        ):
            raise ValueError(
                "weights debe sumar 1.0."
            )

        assets = set(
            portfolio_weights
        )

        if (
            set(benchmark_weights) != assets
            or set(portfolio_returns) != assets
            or set(benchmark_returns) != assets
        ):
            raise ValueError(
                "assets debe coincidir en todas las entradas."
            )

        normalized_assets = tuple(
            portfolio_weights
        )

        portfolio_return = sum(
            float(
                portfolio_weights[asset]
            )
            * float(
                portfolio_returns[asset]
            )
            for asset in normalized_assets
        )

        benchmark_return = sum(
            float(
                benchmark_weights[asset]
            )
            * float(
                benchmark_returns[asset]
            )
            for asset in normalized_assets
        )

        allocation_by_asset: dict[
            str,
            float,
        ] = {}

        selection_by_asset: dict[
            str,
            float,
        ] = {}

        interaction_by_asset: dict[
            str,
            float,
        ] = {}

        asset_contributions: dict[
            str,
            float,
        ] = {}

        for asset in normalized_assets:
            portfolio_weight = float(
                portfolio_weights[asset]
            )

            benchmark_weight = float(
                benchmark_weights[asset]
            )

            portfolio_asset_return = float(
                portfolio_returns[asset]
            )

            benchmark_asset_return = float(
                benchmark_returns[asset]
            )

            allocation = (
                portfolio_weight
                - benchmark_weight
            ) * benchmark_asset_return

            selection = (
                benchmark_weight
                * (
                    portfolio_asset_return
                    - benchmark_asset_return
                )
            )

            interaction = (
                portfolio_weight
                - benchmark_weight
            ) * (
                portfolio_asset_return
                - benchmark_asset_return
            )

            total_contribution = (
                allocation
                + selection
                + interaction
            )

            allocation_by_asset[
                asset
            ] = float(allocation)

            selection_by_asset[
                asset
            ] = float(selection)

            interaction_by_asset[
                asset
            ] = float(interaction)

            asset_contributions[
                asset
            ] = float(total_contribution)

        allocation_effect = sum(
            allocation_by_asset.values()
        )

        selection_effect = sum(
            selection_by_asset.values()
        )

        interaction_effect = sum(
            interaction_by_asset.values()
        )

        active_return = (
            portfolio_return
            - benchmark_return
        )

        best_asset = max(
            asset_contributions,
            key=asset_contributions.get,
        )

        worst_asset = min(
            asset_contributions,
            key=asset_contributions.get,
        )

        return {
            "portfolio_return": float(
                portfolio_return
            ),
            "benchmark_return": float(
                benchmark_return
            ),
            "active_return": float(
                active_return
            ),
            "allocation_effect": float(
                allocation_effect
            ),
            "selection_effect": float(
                selection_effect
            ),
            "interaction_effect": float(
                interaction_effect
            ),
            "allocation_by_asset": (
                allocation_by_asset
            ),
            "selection_by_asset": (
                selection_by_asset
            ),
            "interaction_by_asset": (
                interaction_by_asset
            ),
            "asset_contributions": (
                asset_contributions
            ),
            "best_asset": best_asset,
            "worst_asset": worst_asset,
        }
