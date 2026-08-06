
from __future__ import annotations


class StrategyCertificationRegistryServiceV2:
    """
    Servicio puente entre certificación
    de estrategias y Strategy Registry.
    """


    def __init__(
        self,
        *,
        registry,
    ):

        if not callable(
            getattr(
                registry,
                "register",
                None,
            )
        ):
            raise TypeError(
                "registry debe implementar register()."
            )


        self.registry = registry


    def register_certified_strategy(
        self,
        strategy,
    ):

        certification_status = (
            strategy.get(
                "status"
            )
        )


        if certification_status != "CERTIFIED":

            raise ValueError(
                "Solo estrategias CERTIFIED pueden registrarse."
            )


        return self.registry.register(
            strategy
        )


    def load_default_certified_strategies(
        self,
    ):

        strategy = {
            "strategy_id": "STR-001",
            "name": "EMA50 Smart Money",
            "version": "1.0",
            "status": "CERTIFIED",
            "grade": "A",
            "validation_score": 90,
            "performance_score": 95,
        }


        existing = getattr(
            self.registry,
            "get",
            None,
        )


        if callable(existing):

            try:

                current = existing(
                    strategy["strategy_id"]
                )

                if current is not None:
                    return current

            except ValueError:

                pass


        return self.register_certified_strategy(
            strategy
        )

