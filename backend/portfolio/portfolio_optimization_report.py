from dataclasses import dataclass

from backend.portfolio.portfolio_covariance_matrix import (
    PortfolioCovarianceMatrix,
)
from backend.portfolio.portfolio_maximum_sharpe_optimizer import (
    PortfolioMaximumSharpeOptimizer,
)
from backend.portfolio.portfolio_minimum_variance_optimizer import (
    PortfolioMinimumVarianceOptimizer,
)
from backend.portfolio.portfolio_risk_parity_optimizer import (
    PortfolioRiskParityOptimizer,
)


@dataclass(frozen=True)
class PortfolioOptimizationReport:
    """
    Consolida y compara las principales estrategias
    de optimización de portafolio.
    """

    assets: tuple[str, ...]
    minimum_variance: PortfolioMinimumVarianceOptimizer
    maximum_sharpe: PortfolioMaximumSharpeOptimizer
    risk_parity: PortfolioRiskParityOptimizer
    selected_strategy: str

    @classmethod
    def build(
        cls,
        *,
        covariance_matrix: PortfolioCovarianceMatrix,
        expected_returns: dict[str, float],
        risk_free_rate: float = 0.0,
    ) -> "PortfolioOptimizationReport":
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

        minimum_variance = (
            PortfolioMinimumVarianceOptimizer.optimize(
                covariance_matrix=covariance_matrix,
            )
        )

        maximum_sharpe = (
            PortfolioMaximumSharpeOptimizer.optimize(
                covariance_matrix=covariance_matrix,
                expected_returns=normalized_returns,
                risk_free_rate=risk_free_rate,
            )
        )

        risk_parity = (
            PortfolioRiskParityOptimizer.optimize(
                covariance_matrix=covariance_matrix,
            )
        )

        strategy_scores = {
            "minimum_variance": (
                -minimum_variance.portfolio_volatility
            ),
            "maximum_sharpe": (
                maximum_sharpe.sharpe_ratio
            ),
            "risk_parity": (
                -risk_parity.portfolio_volatility
            ),
        }

        selected_strategy = max(
            strategy_scores,
            key=strategy_scores.get,
        )

        return cls(
            assets=assets,
            minimum_variance=minimum_variance,
            maximum_sharpe=maximum_sharpe,
            risk_parity=risk_parity,
            selected_strategy=selected_strategy,
        )
