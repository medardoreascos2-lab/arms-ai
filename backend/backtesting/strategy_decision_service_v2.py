
from __future__ import annotations



class StrategyDecisionServiceV2:
    """
    Servicio que conecta la recomendación estratégica
    con el motor de decisión final.
    """



    def __init__(
        self,
        *,
        recommendation_service=None,
        selection_service=None,
        decision_engine,
    ):


        if recommendation_service is None and selection_service is None:
            raise TypeError(
                "Debe existir recommendation_service o selection_service."
            )


        if recommendation_service is not None:

            if not callable(
                getattr(
                    recommendation_service,
                    "recommend",
                    None,
                )
            ):
                raise TypeError(
                    "recommendation_service debe implementar recommend()."
                )


        if selection_service is not None:

            if not callable(
                getattr(
                    selection_service,
                    "get_selected_strategy",
                    None,
                )
            ):
                raise TypeError(
                    "selection_service debe implementar get_selected_strategy()."
                )



        if not callable(
            getattr(
                decision_engine,
                "decide",
                None,
            )
        ):
            raise TypeError(
                "decision_engine debe implementar decide()."
            )



        self.recommendation_service = (
            recommendation_service
        )


        self.selection_service = (
            selection_service
        )


        self.decision_engine = (
            decision_engine
        )





    def get_decision(
        self,
        *,
        market_context: dict,
    ) -> dict:
        """
        Alias público para integración
        con dashboard y servicios V2.
        """

        return self.decide(
            market_context=market_context,
        )


    def decide(
        self,
        *,
        market_context: dict,
    ) -> dict:



        if self.selection_service is not None:

            strategy = (
                self.selection_service
                .get_selected_strategy(
                    market_context=market_context,
                )
            )

        else:

            strategy = (
                self.recommendation_service
                .recommend(
                    market_context=market_context,
                )
            )



        return self.decision_engine.decide(
            strategy=strategy,
            market_context=market_context,
        )
