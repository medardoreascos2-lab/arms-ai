
from fastapi import APIRouter



def create_strategy_ranking_router_v2(
    *,
    ranking_service,
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


    router = APIRouter(
        prefix="/api/v2",
        tags=[
            "strategy-ranking-v2",
        ],
    )


    @router.get(
        "/strategies/ranking"
    )
    def get_strategy_ranking():

        return {
            "strategies": (
                ranking_service.rank()
            ),
        }



    return router
