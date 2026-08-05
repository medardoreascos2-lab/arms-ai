
from __future__ import annotations



class StrategyPerformanceDashboardProviderV2:
    """
    Provider encargado de exponer
    rendimiento de estrategias al dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        strategy_performance_service,
    ):


        if not callable(
            getattr(
                strategy_performance_service,
                "get_strategy_performance",
                None,
            )
        ):
            raise TypeError(
                "strategy_performance_service debe implementar get_strategy_performance()."
            )



        self.strategy_performance_service = (
            strategy_performance_service
        )



    def get_strategy_performance(
        self,
    ) -> dict | None:


        return (
            self.strategy_performance_service
            .get_strategy_performance()
        )
