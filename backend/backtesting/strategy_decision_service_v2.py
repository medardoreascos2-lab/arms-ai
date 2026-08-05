
from __future__ import annotations



class StrategyDecisionServiceV2:
    """
    Servicio que conecta la recomendación estratégica
    con el motor de decisión final.
    """



    def __init__(
        self,
        *,
        recommendation_service,
        decision_engine,
    ):


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


        self.decision_engine = (
            decision_engine
        )



    def decide(
        self,
        *,
        market_context: dict,
    ) -> dict:



        strategy = (
            self.recommendation_service.recommend(
                market_context=market_context,
            )
        )



        return self.decision_engine.decide(
            strategy=strategy,
            market_context=market_context,
        )
