from dataclasses import dataclass
from math import sqrt

from backend.portfolio.portfolio_statistics import (
    PortfolioStatistics,
)


@dataclass(frozen=True)
class PortfolioSortinoRatioReport:
    """
    Calcula el Sortino Ratio anualizado usando
    únicamente la desviación negativa.
    """

    sortino_ratio: float
    excess_return: float
    annualized_return: float
    downside_deviation: float
    annualized_downside_deviation: float
    risk_free_rate: float
    sample_size: int
    periods_per_year: int

    @classmethod
    def from_returns(
        cls,
        *,
        returns: list[float] | tuple[float, ...],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 1,
        minimum_acceptable_return: float = 0.0,
    ) -> "PortfolioSortinoRatioReport":
        statistics = PortfolioStatistics.from_returns(
            returns=returns,
            periods_per_year=periods_per_year,
            minimum_acceptable_return=(
                minimum_acceptable_return
            ),
        )

        normalized_risk_free_rate = float(
            risk_free_rate
        )

        excess_return = (
            statistics.annualized_return
            - normalized_risk_free_rate
        )

        annualized_downside_deviation = (
            statistics.downside_deviation
            * sqrt(
                statistics.periods_per_year
            )
        )

        if annualized_downside_deviation == 0:
            sortino_ratio = 0.0
        else:
            sortino_ratio = (
                excess_return
                / annualized_downside_deviation
            )

        return cls(
            sortino_ratio=round(
                sortino_ratio,
                6,
            ),
            excess_return=round(
                excess_return,
                6,
            ),
            annualized_return=(
                statistics.annualized_return
            ),
            downside_deviation=(
                statistics.downside_deviation
            ),
            annualized_downside_deviation=round(
                annualized_downside_deviation,
                6,
            ),
            risk_free_rate=normalized_risk_free_rate,
            sample_size=statistics.sample_size,
            periods_per_year=(
                statistics.periods_per_year
            ),
        )
