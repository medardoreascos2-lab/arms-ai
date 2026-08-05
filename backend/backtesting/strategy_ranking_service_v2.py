
from __future__ import annotations



class StrategyRankingServiceV2:
    """
    Servicio encargado de obtener estrategias
    del registry y generar ranking.
    """


    def __init__(
        self,
        *,
        registry,
        ranking_engine,
    ):

        if not callable(
            getattr(
                registry,
                "list",
                None,
            )
        ):
            raise TypeError(
                "registry debe implementar list()."
            )


        if not callable(
            getattr(
                ranking_engine,
                "rank",
                None,
            )
        ):
            raise TypeError(
                "ranking_engine debe implementar rank()."
            )


        self.registry = registry

        self.ranking_engine = (
            ranking_engine
        )



    def rank(
        self,
    ) -> list[dict]:

        strategies = (
            self.registry.list()
        )


        if not strategies:

            return []



        certified_strategies = [

            strategy

            for strategy

            in strategies

            if strategy.get(
                "status"
            )
            == "CERTIFIED"

        ]



        return self.ranking_engine.rank(
            certified_strategies
        )
