
from __future__ import annotations



def register_router_v2(
    app,
    router,
):
    """
    Registra rutas V2 directamente
    evitando problemas con IncludedRouter.
    """

    for route in router.routes:

        app.router.routes.append(
            route
        )
