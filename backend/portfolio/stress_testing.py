from __future__ import annotations


class StressTesting:
    """
    Aplica shocks por activo sobre un portafolio
    y calcula su impacto económico.
    """

    def calculate(
        self,
        *,
        weights: dict[str, float],
        shocks: dict[str, float],
        initial_value: float = 1000.0,
    ) -> dict[str, object]:
        if initial_value <= 0.0:
            raise ValueError(
                "initial_value debe ser mayor que cero."
            )

        if not weights:
            raise ValueError(
                "weights no puede estar vacío."
            )

        normalized_weights = {
            str(symbol).strip().upper(): float(weight)
            for symbol, weight in weights.items()
        }

        weight_sum = sum(
            normalized_weights.values()
        )

        if abs(weight_sum - 1.0) > 1e-9:
            raise ValueError(
                "weights debe sumar 1.0."
            )

        normalized_shocks = {
            str(symbol).strip().upper(): float(shock)
            for symbol, shock in shocks.items()
        }

        missing_shocks = (
            set(normalized_weights)
            - set(normalized_shocks)
        )

        if missing_shocks:
            raise ValueError(
                "shocks debe incluir todos los activos."
            )

        asset_impacts = {
            symbol: (
                initial_value
                * weight
                * normalized_shocks[symbol]
            )
            for symbol, weight
            in normalized_weights.items()
        }

        absolute_loss = sum(
            asset_impacts.values()
        )

        final_value = (
            initial_value
            + absolute_loss
        )

        percentage_loss = (
            absolute_loss
            / initial_value
        )

        worst_asset = min(
            asset_impacts,
            key=asset_impacts.get,
        )

        best_asset = max(
            asset_impacts,
            key=asset_impacts.get,
        )

        return {
            "initial_value": float(
                initial_value
            ),
            "final_value": float(
                final_value
            ),
            "absolute_loss": float(
                absolute_loss
            ),
            "percentage_loss": float(
                percentage_loss
            ),
            "asset_impacts": {
                symbol: float(value)
                for symbol, value
                in asset_impacts.items()
            },
            "worst_asset": worst_asset,
            "best_asset": best_asset,
        }
