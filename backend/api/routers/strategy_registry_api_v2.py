
from fastapi import APIRouter



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


    return router
