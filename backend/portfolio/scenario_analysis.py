from __future__ import annotations


class ScenarioAnalysis:
    """
    Aplica escenarios predefinidos sobre un portafolio.
    """

    SCENARIOS: dict[str, float] = {
        "financial_crisis_2008": -0.40,
        "covid_2020": -0.30,
        "technology_shock": -0.35,
        "rate_hike": -0.15,
    }

    def available_scenarios(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            self.SCENARIOS
        )

    def calculate(
        self,
        *,
        weights: dict[str, float],
        scenario: str,
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
            for symbol, weight
            in weights.items()
        }

        weight_sum = sum(
            normalized_weights.values()
        )

        if abs(weight_sum - 1.0) > 1e-9:
            raise ValueError(
                "weights debe sumar 1.0."
            )

        normalized_scenario = (
            scenario
            .strip()
            .lower()
        )

        if (
            normalized_scenario
            not in self.SCENARIOS
        ):
            raise ValueError(
                "scenario no reconocido."
            )

        scenario_shock = self.SCENARIOS[
            normalized_scenario
        ]

        shocks = {
            symbol: float(
                scenario_shock
            )
            for symbol
            in normalized_weights
        }

        asset_impacts = {
            symbol: (
                initial_value
                * weight
                * shocks[symbol]
            )
            for symbol, weight
            in normalized_weights.items()
        }

        absolute_impact = sum(
            asset_impacts.values()
        )

        final_value = (
            initial_value
            + absolute_impact
        )

        percentage_impact = (
            absolute_impact
            / initial_value
        )

        return {
            "scenario": (
                normalized_scenario
            ),
            "initial_value": float(
                initial_value
            ),
            "final_value": float(
                final_value
            ),
            "absolute_impact": float(
                absolute_impact
            ),
            "percentage_impact": float(
                percentage_impact
            ),
            "shocks": shocks,
            "asset_impacts": {
                symbol: float(value)
                for symbol, value
                in asset_impacts.items()
            },
        }
