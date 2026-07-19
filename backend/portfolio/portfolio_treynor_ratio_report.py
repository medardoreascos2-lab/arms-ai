from dataclasses import dataclass

from backend.portfolio.portfolio_beta_report import (
    PortfolioBetaReport,
)
from backend.portfolio.portfolio_statistics import (
    PortfolioStatistics,
)


@dataclass(frozen=True)
class PortfolioTreynorRatioReport:
    """
    Calcula el Treynor Ratio anualizado de un
    portafolio frente a un benchmark.
    """

    treynor_ratio: float
    excess_return: float
    annualized_return: float
    beta: float
    risk_free_rate: float
    classification: str
    sample_size: int
    periods_per_year: int

    @classmethod
    def from_returns(
        cls,
        *,
        portfolio_returns: list[float] | tuple[float, ...],
        benchmark_returns: list[float] | tuple[float, ...],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 1,
    ) -> "PortfolioTreynorRatioReport":
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

        statistics = PortfolioStatistics.from_returns(
            returns=portfolio_returns,
            periods_per_year=periods_per_year,
        )

        beta_report = PortfolioBetaReport.from_returns(
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
        )

        normalized_risk_free_rate = float(
            risk_free_rate
        )

        excess_return = round(
            statistics.annualized_return
            - normalized_risk_free_rate,
            6,
        )

        if beta_report.beta == 0:
            treynor_ratio = 0.0
        else:
            treynor_ratio = (
                excess_return
                / beta_report.beta
            )

        return cls(
            treynor_ratio=round(
                treynor_ratio,
                6,
            ),
            excess_return=excess_return,
            annualized_return=(
                statistics.annualized_return
            ),
            beta=beta_report.beta,
            risk_free_rate=normalized_risk_free_rate,
            classification=(
                beta_report.classification
            ),
            sample_size=statistics.sample_size,
            periods_per_year=(
                statistics.periods_per_year
            ),
        )
