from backend.portfolio.portfolio_optimization_recommendation import (
    PortfolioOptimizationRecommendation,
)


class PortfolioOptimizationExporter:
    """
    Convierte una recomendación de optimización
    en un diccionario serializable.
    """

    @staticmethod
    def to_dict(
        *,
        recommendation: PortfolioOptimizationRecommendation,
    ) -> dict:
        if not isinstance(
            recommendation,
            PortfolioOptimizationRecommendation,
        ):
            raise TypeError(
                "recommendation debe ser "
                "PortfolioOptimizationRecommendation."
            )

        rebalancing_payload = None

        if recommendation.rebalancing is not None:
            rebalancing = recommendation.rebalancing

            rebalancing_payload = {
                "assets": list(
                    rebalancing.assets
                ),
                "current_weights": dict(
                    rebalancing.current_weights
                ),
                "target_weights": dict(
                    rebalancing.target_weights
                ),
                "trades": dict(
                    rebalancing.trades
                ),
                "turnover": rebalancing.turnover,
                "overweight_assets": list(
                    rebalancing.overweight_assets
                ),
                "underweight_assets": list(
                    rebalancing.underweight_assets
                ),
                "tolerance": rebalancing.tolerance,
            }

        return {
            "strategy": recommendation.strategy,
            "risk_level": recommendation.risk_level,
            "target_weights": dict(
                recommendation.target_weights
            ),
            "explanation": recommendation.explanation,
            "metrics": {
                "expected_return": (
                    recommendation.expected_return
                ),
                "portfolio_volatility": (
                    recommendation.portfolio_volatility
                ),
                "sharpe_ratio": (
                    recommendation.sharpe_ratio
                ),
            },
            "rebalancing": rebalancing_payload,
        }
