from __future__ import annotations


class StrategySelectionDashboardProviderV2:
    """
    Provider encargado de exponer la estrategia
    seleccionada por ARMS AI al dashboard.
    """


    def __init__(
        self,
        *,
        strategy_selection_service,
    ):


        if not callable(
            getattr(
                strategy_selection_service,
                "select",
                None,
            )
        ):
            raise TypeError(
                "strategy_selection_service debe implementar select()."
            )


        self.strategy_selection_service = (
            strategy_selection_service
        )



    def get_selection(
        self,
        *,
        market_context: dict,
    ) -> dict | None:


        return (
            self.strategy_selection_service
            .select(
                market_context=market_context,
            )
        )
