
from __future__ import annotations



class StrategyRankingDashboardProviderV2:
    """
    Provider encargado de exponer
    ranking de estrategias al dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        strategy_ranking_service,
    ):


        if not callable(
            getattr(
                strategy_ranking_service,
                "get_ranking",
                None,
            )
        ):

            raise TypeError(
                "strategy_ranking_service debe implementar get_ranking()."
            )


        self.strategy_ranking_service = (
            strategy_ranking_service
        )



    def get_ranking(
        self,
    ) -> dict | None:


        return (
            self.strategy_ranking_service
            .get_ranking()
        )
