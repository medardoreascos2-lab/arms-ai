
from __future__ import annotations



class StrategyRegistryDashboardProviderV2:
    """
    Provider para exponer estrategias registradas
    dentro del Dashboard V2.
    """


    def __init__(
        self,
        *,
        registry,
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


        self.registry = registry



    def get_strategies(
        self,
    ):

        strategies = (
            self.registry.list()
        )


        certified = [
            strategy
            for strategy
            in strategies
            if strategy.get(
                "status"
            ) == "CERTIFIED"
        ]


        return {
            "total": len(
                strategies
            ),
            "certified": len(
                certified
            ),
            "items": strategies,
        }
