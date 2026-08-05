
from __future__ import annotations



class PerformanceDashboardProviderV2:
    """
    Provider encargado de exponer métricas
    de rendimiento para el dashboard ARMS AI.
    """



    def __init__(
        self,
        *,
        performance_service,
    ):


        if not callable(
            getattr(
                performance_service,
                "get_performance",
                None,
            )
        ):
            raise TypeError(
                "performance_service debe implementar get_performance()."
            )



        self.performance_service = (
            performance_service
        )



    def get_performance(
        self,
    ) -> dict | None:


        result = (
            self.performance_service
            .get_performance()
        )


        if result is None:

            return None


        if (
            result.get(
                "total_trades"
            )
            == 0
        ):

            return None


        return result
