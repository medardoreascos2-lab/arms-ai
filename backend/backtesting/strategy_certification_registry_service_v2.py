
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
