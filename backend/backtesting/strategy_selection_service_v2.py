from __future__ import annotations


class StrategySelectionServiceV2:
    """
    Servicio encargado de conectar el ranking
    de estrategias con el motor de selección.
    """


    def __init__(
        self,
        *,
        ranking_service,
        selection_engine,
    ):


        if not callable(
            getattr(
                ranking_service,
                "rank",
                None,
            )
        ):
            raise TypeError(
                "ranking_service debe implementar rank()."
            )


        if not callable(
            getattr(
                selection_engine,
                "select",
                None,
            )
        ):
            raise TypeError(
                "selection_engine debe implementar select()."
            )


        self.ranking_service = (
            ranking_service
        )


        self.selection_engine = (
            selection_engine
        )



    def select(
        self,
        *,
        market_context: dict,
    ) -> dict | None:


        ranking_result = (
            self.ranking_service.rank()
        )


        if not ranking_result:

            return {
                "status": "BLOCKED",
                "reason": "NO_STRATEGIES",
            }



        if isinstance(
            ranking_result,
            dict,
        ):

            strategies = (
                ranking_result.get(
                    "ranking",
                    []
                )
            )

        else:

            strategies = ranking_result



        return self.selection_engine.select(
            strategies=strategies,
            market_context=market_context,
        )
