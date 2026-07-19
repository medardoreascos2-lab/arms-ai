from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_efficient_frontier import (
    PortfolioEfficientFrontier,
)


@dataclass(frozen=True)
class PortfolioMaximumSharpeOptimizer:
    """
    Selecciona el portafolio con mayor Sharpe Ratio
    dentro de una frontera eficiente determinista.
    """

    assets: tuple[str, ...]
    weights: Mapping[str, float]
    expected_return: float
    portfolio_volatility: float
    excess_return: float
    sharpe_ratio: float
    risk_free_rate: float

    @classmethod
    def optimize(
        cls,
        *,
        covariance_matrix: PortfolioCovarianceMatrix,
        expected_returns: dict[str, float],
        risk_free_rate: float = 0.0,
        frontier_points: int = 101,
    ) -> "PortfolioMaximumSharpeOptimizer":
        if not isinstance(
            covariance_matrix,
            PortfolioCovarianceMatrix,
        ):
            raise TypeError(
                "covariance_matrix debe ser "
                "PortfolioCovarianceMatrix."
            )

        if not expected_returns:
            raise ValueError(
                "expected_returns no puede estar vacío."
            )

        if frontier_points <= 0:
            raise ValueError(
                "frontier_points debe ser mayor que cero."
            )

        normalized_returns = {
            symbol.strip().upper(): float(value)
            for symbol, value in expected_returns.items()
        }

        assets = covariance_matrix.assets

        if set(normalized_returns) != set(assets):
            raise ValueError(
                "expected_returns debe contener "
                "los mismos activos que covariance_matrix."
            )

        normalized_risk_free_rate = float(
            risk_free_rate
        )

        frontier = PortfolioEfficientFrontier.generate(
            covariance_matrix=covariance_matrix,
            points=frontier_points,
        )

        best_portfolio = None
        best_expected_return = 0.0
        best_excess_return = 0.0
        best_sharpe_ratio = float("-inf")

        for portfolio in frontier.portfolios:
            expected_return = sum(
                (
                    portfolio.weights[asset]
                    / 100.0
                )
                * normalized_returns[asset]
                for asset in assets
            )

            excess_return = (
                expected_return
                - normalized_risk_free_rate
            )

            if portfolio.portfolio_volatility == 0:
                sharpe_ratio = 0.0
            else:
                sharpe_ratio = (
                    excess_return
                    / portfolio.portfolio_volatility
                )

            if sharpe_ratio > best_sharpe_ratio:
                best_portfolio = portfolio
                best_expected_return = expected_return
                best_excess_return = excess_return
                best_sharpe_ratio = sharpe_ratio

        if best_portfolio is None:
            raise RuntimeError(
                "No fue posible seleccionar un portafolio."
            )

        return cls(
            assets=assets,
            weights=MappingProxyType(
                dict(best_portfolio.weights)
            ),
            expected_return=round(
                best_expected_return,
                6,
            ),
            portfolio_volatility=(
                best_portfolio.portfolio_volatility
            ),
            excess_return=round(
                best_excess_return,
                6,
            ),
            sharpe_ratio=round(
                best_sharpe_ratio,
                6,
            ),
            risk_free_rate=normalized_risk_free_rate,
        )
