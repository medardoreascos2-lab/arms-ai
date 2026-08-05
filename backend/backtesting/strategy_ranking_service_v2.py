
from __future__ import annotations



class StrategyRankingServiceV2:
    """
    Servicio encargado de obtener estrategias
    del registry y generar ranking.
    """


    def __init__(
        self,
        *,
        registry=None,
        ranking_engine=None,
        strategy_provider=None,
        engine=None,
    ):

        if strategy_provider is not None:

            registry = strategy_provider


        if engine is not None:

            ranking_engine = engine



        if not callable(
            getattr(
                registry,
                "list",
                None,
            )
        ) and not callable(
            getattr(
                registry,
                "get_strategies",
                None,
            )
        ):
            raise TypeError(
                "registry debe implementar list() o get_strategies()."
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




    def get_ranking(
        self,
    ) -> dict:


        if callable(
            getattr(
                self.registry,
                "get_strategies",
                None,
            )
        ):

            strategies = (
                self.registry
                .get_strategies()
            )

        else:

            strategies = (
                self.registry
                .list()
            )


        if strategies is None:

            return {
                "status": "BLOCKED",
                "reason": "INVALID_HISTORY",
            }


        return self.ranking_engine.rank(
            strategies
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
