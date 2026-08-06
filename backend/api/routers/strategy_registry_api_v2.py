
from fastapi import APIRouter, HTTPException



def create_strategy_registry_router_v2(
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


    router = APIRouter(
        prefix="/api/v2",
        tags=[
            "strategy-registry-v2",
        ],
    )


    @router.get("/strategies")
    def list_strategies():

        return {
            "strategies": (
                registry.list()
            ),
        }





    @router.get(
        "/strategies/{strategy_id}"
    )
    def get_strategy(
        strategy_id: str,
    ):

        try:

            return registry.get(
                strategy_id
            )

        except ValueError:

            raise HTTPException(
                status_code=404,
                detail="Estrategia no encontrada.",
            )


    return router
