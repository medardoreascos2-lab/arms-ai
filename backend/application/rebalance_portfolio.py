from backend.portfolio.portfolio_rebalancing_engine import (
    PortfolioRebalancingEngine,
)


class RebalancePortfolio:
    """
    Caso de uso para calcular el rebalanceo
    de un portafolio.
    """

    def __init__(
        self,
        *,
        engine=PortfolioRebalancingEngine,
    ) -> None:
        rebalance_method = getattr(
            engine,
            "rebalance",
            None,
        )

        if not callable(rebalance_method):
            raise TypeError(
                "engine debe exponer un método rebalance."
            )

        self._engine = engine

    def execute(
        self,
        *,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        tolerance: float = 0.0,
    ) -> PortfolioRebalancingEngine:
        return self._engine.rebalance(
            current_weights=current_weights,
            target_weights=target_weights,
            tolerance=tolerance,
        )
