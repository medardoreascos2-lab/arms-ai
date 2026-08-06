from __future__ import annotations


class ExecutionServiceV2:
    """
    Servicio encargado de coordinar
    validación de riesgo y ejecución.
    """


    def __init__(
        self,
        *,
        risk_service,
        execution_engine,
    ):


        if not callable(
            getattr(
                risk_service,
                "validate_trade",
                None,
            )
        ):
            raise TypeError(
                "risk_service debe implementar validate_trade()."
            )


        if not callable(
            getattr(
                execution_engine,
                "execute",
                None,
            )
        ):
            raise TypeError(
                "execution_engine debe implementar execute()."
            )


        self.risk_service = (
            risk_service
        )


        self.execution_engine = (
            execution_engine
        )



    def execute(
        self,
        *,
        trade_plan: dict,
    ) -> dict:


        risk_validation = (
            self.risk_service.validate_trade(
                trade_plan=trade_plan,
            )
        )


        return self.execution_engine.execute(
            risk_validation=risk_validation,
            trade_plan=trade_plan,
        )
