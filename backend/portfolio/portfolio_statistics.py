from dataclasses import dataclass
from math import prod, sqrt
from statistics import mean, stdev


@dataclass(frozen=True)
class PortfolioStatistics:
    """
    Calcula estadísticas descriptivas sobre
    una serie de rendimientos.
    """

    mean_return: float
    volatility: float
    annualized_return: float
    annualized_volatility: float
    downside_deviation: float
    cumulative_return: float
    sample_size: int
    periods_per_year: int
    minimum_acceptable_return: float

    @classmethod
    def from_returns(
        cls,
        *,
        returns: list[float] | tuple[float, ...],
        periods_per_year: int = 1,
        minimum_acceptable_return: float = 0.0,
    ) -> "PortfolioStatistics":
        if not returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        if len(returns) < 2:
            raise ValueError(
                "returns debe contener al menos 2 valores."
            )

        if periods_per_year <= 0:
            raise ValueError(
                "periods_per_year debe ser mayor que cero."
            )

        normalized_returns = tuple(
            float(value)
            for value in returns
        )

        minimum_acceptable_return = float(
            minimum_acceptable_return
        )

        mean_return = mean(
            normalized_returns
        )

        volatility = stdev(
            normalized_returns
        )

        downside_squared_deviations = [
            min(
                0.0,
                value
                - minimum_acceptable_return,
            ) ** 2
            for value in normalized_returns
        ]

        downside_deviation = sqrt(
            sum(
                downside_squared_deviations
            )
            / len(
                downside_squared_deviations
            )
        )

        cumulative_return = (
            prod(
                1.0 + value
                for value in normalized_returns
            )
            - 1.0
        )

        rounded_mean_return = round(
            mean_return,
            6,
        )
        rounded_volatility = round(
            volatility,
            6,
        )

        annualized_return = (
            rounded_mean_return
            * periods_per_year
        )

        annualized_volatility = (
            rounded_volatility
            * sqrt(periods_per_year)
        )

        return cls(
            mean_return=rounded_mean_return,
            volatility=rounded_volatility,
            annualized_return=round(
                annualized_return,
                6,
            ),
            annualized_volatility=round(
                annualized_volatility,
                6,
            ),
            downside_deviation=round(
                downside_deviation,
                6,
            ),
            cumulative_return=round(
                cumulative_return,
                6,
            ),
            sample_size=len(
                normalized_returns
            ),
            periods_per_year=int(
                periods_per_year
            ),
            minimum_acceptable_return=(
                minimum_acceptable_return
            ),
        )
