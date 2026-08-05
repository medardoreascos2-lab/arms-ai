
from fastapi import APIRouter



def create_strategy_recommendation_router_v2(
    *,
    recommendation_service,
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



    router = APIRouter(
        prefix="/api/v2",
        tags=[
            "strategy-recommendation-v2",
        ],
    )



    @router.get(
        "/strategies/recommendation"
    )
    def recommend_strategy(
        regime: str,
        volatility: str,
    ):


        result = recommendation_service.recommend(
            market_context={
                "regime": regime,
                "volatility": volatility,
            }
        )


        return {
            "strategy": result,
            **(
                result
                if result is not None
                else {}
            ),
        }



    return router
