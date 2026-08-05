from __future__ import annotations

from fastapi import APIRouter


def create_backtesting_metrics_router_v2(
    *,
    metrics_provider,
) -> APIRouter:
    """
    Router REST para exponer métricas
    del sistema de backtesting.
    """

    if not callable(
        getattr(
            metrics_provider,
            "get_metrics",
            None,
        )
    ):
        raise TypeError(
            "metrics_provider debe implementar "
            "get_metrics()."
        )

    router = APIRouter(
        prefix="/api/v2/backtesting",
        tags=[
            "backtesting-metrics-v2",
        ],
    )

    @router.get("/metrics")
    def get_metrics():

        return {
            "metrics": (
                metrics_provider
                .get_metrics()
            ),
        }

    return router
