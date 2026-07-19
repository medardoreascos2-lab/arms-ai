from dataclasses import dataclass
from math import sqrt
from statistics import mean, stdev


@dataclass(frozen=True)
class PortfolioTrackingErrorReport:
    """
    Calcula los retornos activos y el tracking error
    de un portafolio frente a un benchmark.
    """

    mean_active_return: float
    tracking_error: float
    annualized_tracking_error: float
    sample_size: int
    periods_per_year: int

    @classmethod
    def from_returns(
        cls,
        *,
        portfolio_returns: list[float] | tuple[float, ...],
        benchmark_returns: list[float] | tuple[float, ...],
        periods_per_year: int = 1,
    ) -> "PortfolioTrackingErrorReport":
        if not portfolio_returns or not benchmark_returns:
            raise ValueError(
                "returns no puede estar vacío."
            )

        if len(portfolio_returns) != len(
            benchmark_returns
        ):
            raise ValueError(
                "portfolio_returns y benchmark_returns "
                "deben tener la misma length."
            )

        if len(portfolio_returns) < 2:
            raise ValueError(
                "returns debe contener al menos 2 valores."
            )

        if periods_per_year <= 0:
            raise ValueError(
                "periods_per_year debe ser mayor que cero."
            )

        normalized_portfolio = tuple(
            float(value)
            for value in portfolio_returns
        )
        normalized_benchmark = tuple(
            float(value)
            for value in benchmark_returns
        )

        active_returns = tuple(
            portfolio_value - benchmark_value
            for portfolio_value, benchmark_value in zip(
                normalized_portfolio,
                normalized_benchmark,
            )
        )

        mean_active_return = round(
            mean(active_returns),
            6,
        )

        tracking_error = round(
            stdev(active_returns),
            6,
        )

        annualized_tracking_error = round(
            tracking_error
            * sqrt(periods_per_year),
            6,
        )

        return cls(
            mean_active_return=mean_active_return,
            tracking_error=tracking_error,
            annualized_tracking_error=(
                annualized_tracking_error
            ),
            sample_size=len(active_returns),
            periods_per_year=int(
                periods_per_year
            ),
        )
