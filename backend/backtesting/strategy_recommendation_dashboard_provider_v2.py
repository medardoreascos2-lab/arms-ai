
from __future__ import annotations



class StrategyRecommendationDashboardProviderV2:
    """
    Provider que expone la recomendación estratégica
    para el dashboard de backtesting ARMS AI.
    """



    def __init__(
        self,
        *,
        recommendation_service,
        market_context_provider=None,
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


        self.recommendation_service = (
            recommendation_service
        )

        self.market_context_provider = (
            market_context_provider
        )



    def get_recommendation(
        self,
    ) -> dict | None:


        if self.market_context_provider:

            market_context = (
                self.market_context_provider()
            )

        else:

            market_context = {
                "regime": "TRENDING",
                "volatility": "LOW_VOLATILITY",
            }



        return self.recommendation_service.recommend(
            market_context=market_context,
        )
