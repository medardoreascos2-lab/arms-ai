from dataclasses import dataclass

from backend.portfolio.portfolio_statistics import (
    PortfolioStatistics,
)


@dataclass(frozen=True)
class PortfolioSharpeRatioReport:
    """
    Calcula el Sharpe Ratio anualizado de una
    serie de rendimientos.
    """

    sharpe_ratio: float
    excess_return: float
    annualized_return: float
    annualized_volatility: float
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
    ) -> "PortfolioSharpeRatioReport":
        statistics = PortfolioStatistics.from_returns(
            returns=returns,
            periods_per_year=periods_per_year,
        )

        normalized_risk_free_rate = float(
            risk_free_rate
        )

        excess_return = (
            statistics.annualized_return
            - normalized_risk_free_rate
        )

        if statistics.annualized_volatility == 0:
            sharpe_ratio = 0.0
        else:
            sharpe_ratio = (
                excess_return
                / statistics.annualized_volatility
            )

        return cls(
            sharpe_ratio=round(
                sharpe_ratio,
                6,
            ),
            excess_return=round(
                excess_return,
                6,
            ),
            annualized_return=(
                statistics.annualized_return
            ),
            annualized_volatility=(
                statistics.annualized_volatility
            ),
            risk_free_rate=normalized_risk_free_rate,
            sample_size=statistics.sample_size,
            periods_per_year=(
                statistics.periods_per_year
            ),
        )
