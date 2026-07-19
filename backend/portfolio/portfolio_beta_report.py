from dataclasses import dataclass
from statistics import covariance, variance


@dataclass(frozen=True)
class PortfolioBetaReport:
    """
    Calcula la beta de un portafolio frente
    a un benchmark.
    """

    beta: float
    covariance: float
    benchmark_variance: float
    classification: str
    sample_size: int

    @classmethod
    def from_returns(
        cls,
        *,
        portfolio_returns: list[float] | tuple[float, ...],
        benchmark_returns: list[float] | tuple[float, ...],
    ) -> "PortfolioBetaReport":
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

        normalized_portfolio = tuple(
            float(value)
            for value in portfolio_returns
        )
        normalized_benchmark = tuple(
            float(value)
            for value in benchmark_returns
        )

        portfolio_market_covariance = covariance(
            normalized_portfolio,
            normalized_benchmark,
        )

        benchmark_variance = variance(
            normalized_benchmark
        )

        if benchmark_variance == 0:
            beta = 0.0
        else:
            beta = (
                portfolio_market_covariance
                / benchmark_variance
            )

        if beta < 0.9:
            classification = "Defensive"
        elif beta <= 1.1:
            classification = "Neutral"
        else:
            classification = "Aggressive"

        return cls(
            beta=round(
                beta,
                6,
            ),
            covariance=round(
                portfolio_market_covariance,
                6,
            ),
            benchmark_variance=round(
                benchmark_variance,
                6,
            ),
            classification=classification,
            sample_size=len(
                normalized_portfolio
            ),
        )
