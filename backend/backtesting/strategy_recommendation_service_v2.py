
from __future__ import annotations



class StrategyRecommendationServiceV2:
    """
    Servicio encargado de recomendar la mejor estrategia
    usando ranking y contexto actual del mercado.
    """



    def __init__(
        self,
        *,
        ranking_service,
        recommendation_engine,
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
                recommendation_engine,
                "recommend",
                None,
            )
        ):
            raise TypeError(
                "recommendation_engine debe implementar recommend()."
            )



        self.ranking_service = (
            ranking_service
        )


        self.recommendation_engine = (
            recommendation_engine
        )



    def recommend(
        self,
        *,
        market_context: dict,
    ) -> dict | None:



        strategies = (
            self.ranking_service.rank()
        )



        if not strategies:

            return None



        return self.recommendation_engine.recommend(
            strategies=strategies,
            market_context=market_context,
        )
