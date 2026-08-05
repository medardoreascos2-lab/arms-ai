
from __future__ import annotations


class StrategyRegistryV2:
    """
    Registro central de estrategias certificadas
    para ARMS AI.
    """


    REQUIRED_FIELDS = {
        "strategy_id",
        "name",
        "version",
        "status",
        "grade",
        "validation_score",
        "performance_score",
    }


    def __init__(
        self,
    ):

        self._strategies = {}


    def register(
        self,
        strategy: dict,
    ):

        self._validate(
            strategy
        )


        strategy_id = (
            strategy["strategy_id"]
        )


        if strategy_id in self._strategies:

            raise ValueError(
                "La estrategia ya existe."
            )


        self._strategies[strategy_id] = (
            strategy.copy()
        )


        return strategy.copy()


    def get(
        self,
        strategy_id: str,
    ):

        if strategy_id not in self._strategies:

            raise ValueError(
                "Estrategia no encontrada."
            )


        return (
            self._strategies[strategy_id]
            .copy()
        )


    def list(
        self,
    ):

        return [
            strategy.copy()
            for strategy
            in self._strategies.values()
        ]


    def _validate(
        self,
        strategy: dict,
    ):

        if not isinstance(
            strategy,
            dict,
        ):
            raise ValueError(
                "strategy debe ser un dict."
            )


        missing = (
            self.REQUIRED_FIELDS
            -
            set(strategy.keys())
        )


        if missing:

            raise ValueError(
                "strategy incompleta."
            )
