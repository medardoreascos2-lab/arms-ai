from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from backend.portfolio.portfolio_optimization_report import (
    PortfolioOptimizationReport,
)
from backend.portfolio.portfolio_rebalancing_engine import (
    PortfolioRebalancingEngine,
)


@dataclass(frozen=True)
class PortfolioOptimizationRecommendation:
    """
    Traduce un reporte de optimización en una
    recomendación lista para dashboard o IA.
    """

    strategy: str
    target_weights: Mapping[str, float]
    risk_level: str
    explanation: str
    expected_return: float | None
    portfolio_volatility: float
    sharpe_ratio: float | None
    rebalancing: PortfolioRebalancingEngine | None

    @classmethod
    def from_report(
        cls,
        *,
        report: PortfolioOptimizationReport,
        current_weights: dict[str, float] | None = None,
        tolerance: float = 0.0,
    ) -> "PortfolioOptimizationRecommendation":
        if not isinstance(
            report,
            PortfolioOptimizationReport,
        ):
            raise TypeError(
                "report debe ser "
                "PortfolioOptimizationReport."
            )

        strategy = report.selected_strategy

        if strategy == "minimum_variance":
            selected = report.minimum_variance
            target_weights = selected.weights
            expected_return = None
            portfolio_volatility = (
                selected.portfolio_volatility
            )
            sharpe_ratio = None
        elif strategy == "maximum_sharpe":
            selected = report.maximum_sharpe
            target_weights = selected.weights
            expected_return = selected.expected_return
            portfolio_volatility = (
                selected.portfolio_volatility
            )
            sharpe_ratio = selected.sharpe_ratio
        elif strategy == "risk_parity":
            selected = report.risk_parity
            target_weights = selected.weights
            expected_return = None
            portfolio_volatility = (
                selected.portfolio_volatility
            )
            sharpe_ratio = None
        else:
            raise ValueError(
                "Estrategia de optimización no reconocida."
            )

        if portfolio_volatility < 0.12:
            risk_level = "conservative"
        elif portfolio_volatility < 0.25:
            risk_level = "moderate"
        else:
            risk_level = "aggressive"

        explanation = (
            f"strategy={strategy}; "
            f"risk_level={risk_level}; "
            f"portfolio_volatility="
            f"{portfolio_volatility:.6f}"
        )

        if sharpe_ratio is not None:
            explanation += (
                f"; sharpe_ratio={sharpe_ratio:.6f}"
            )

        if current_weights is None:
            rebalancing = None
        else:
            rebalancing = (
                PortfolioRebalancingEngine.rebalance(
                    current_weights=current_weights,
                    target_weights=dict(
                        target_weights
                    ),
                    tolerance=tolerance,
                )
            )

        return cls(
            strategy=strategy,
            target_weights=MappingProxyType(
                dict(target_weights)
            ),
            risk_level=risk_level,
            explanation=explanation,
            expected_return=expected_return,
            portfolio_volatility=(
                portfolio_volatility
            ),
            sharpe_ratio=sharpe_ratio,
            rebalancing=rebalancing,
        )
