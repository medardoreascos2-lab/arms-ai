from dataclasses import dataclass
from random import Random
from statistics import mean, median


@dataclass(frozen=True)
class PortfolioMonteCarloEngine:
    """
    Ejecuta simulaciones Monte Carlo sobre el valor
    futuro de un portafolio.
    """

    initial_value: float
    mean_return: float
    volatility: float
    periods: int
    simulations: int
    seed: int | None

    final_values: tuple[float, ...]

    mean_final_value: float
    median_final_value: float
    minimum_final_value: float
    maximum_final_value: float
    percentile_5: float
    percentile_95: float
    probability_of_loss: float

    @classmethod
    def run(
        cls,
        *,
        initial_value: float,
        mean_return: float,
        volatility: float,
        periods: int,
        simulations: int,
        seed: int | None = None,
    ) -> "PortfolioMonteCarloEngine":
        initial_value = float(initial_value)
        mean_return = float(mean_return)
        volatility = float(volatility)

        if initial_value <= 0:
            raise ValueError(
                "initial_value debe ser mayor que cero."
            )

        if periods <= 0:
            raise ValueError(
                "periods debe ser mayor que cero."
            )

        if simulations <= 0:
            raise ValueError(
                "simulations debe ser mayor que cero."
            )

        if volatility < 0:
            raise ValueError(
                "volatility no puede ser negativa."
            )

        random_generator = Random(seed)

        final_values: list[float] = []

        for _ in range(simulations):
            simulated_value = initial_value

            for _ in range(periods):
                period_return = random_generator.gauss(
                    mean_return,
                    volatility,
                )

                simulated_value *= (
                    1.0
                    + period_return
                )

            final_values.append(
                round(
                    simulated_value,
                    6,
                )
            )

        ordered_values = sorted(
            final_values
        )

        percentile_5 = cls._percentile(
            ordered_values,
            0.05,
        )
        percentile_95 = cls._percentile(
            ordered_values,
            0.95,
        )

        losing_simulations = sum(
            value < initial_value
            for value in final_values
        )

        probability_of_loss = (
            losing_simulations
            / simulations
            * 100
        )

        return cls(
            initial_value=initial_value,
            mean_return=mean_return,
            volatility=volatility,
            periods=int(periods),
            simulations=int(simulations),
            seed=seed,
            final_values=tuple(final_values),
            mean_final_value=round(
                mean(final_values),
                6,
            ),
            median_final_value=round(
                median(final_values),
                6,
            ),
            minimum_final_value=round(
                min(final_values),
                6,
            ),
            maximum_final_value=round(
                max(final_values),
                6,
            ),
            percentile_5=round(
                percentile_5,
                6,
            ),
            percentile_95=round(
                percentile_95,
                6,
            ),
            probability_of_loss=round(
                probability_of_loss,
                2,
            ),
        )

    @staticmethod
    def _percentile(
        ordered_values: list[float],
        probability: float,
    ) -> float:
        if len(ordered_values) == 1:
            return ordered_values[0]

        position = (
            len(ordered_values) - 1
        ) * probability

        lower_index = int(position)
        upper_index = min(
            lower_index + 1,
            len(ordered_values) - 1,
        )

        fraction = (
            position
            - lower_index
        )

        lower_value = ordered_values[
            lower_index
        ]
        upper_value = ordered_values[
            upper_index
        ]

        return (
            lower_value
            + (
                upper_value
                - lower_value
            )
            * fraction
        )
