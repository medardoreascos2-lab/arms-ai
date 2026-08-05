
from __future__ import annotations



class RiskValidationServiceV2:
    """
    Servicio encargado de conectar el Trade Plan
    con el motor de validación de riesgo.
    """



    def __init__(
        self,
        *,
        trade_plan_service,
        risk_engine,
    ):


        if not callable(
            getattr(
                trade_plan_service,
                "generate",
                None,
            )
        ):
            raise TypeError(
                "trade_plan_service debe implementar generate()."
            )



        if not callable(
            getattr(
                risk_engine,
                "validate",
                None,
            )
        ):
            raise TypeError(
                "risk_engine debe implementar validate()."
            )



        self.trade_plan_service = (
            trade_plan_service
        )


        self.risk_engine = (
            risk_engine
        )



    def validate(
        self,
        *,
        market_context: dict,
        market_data: dict,
        account_state: dict,
        risk_config: dict,
    ) -> dict:



        trade_plan = (
            self.trade_plan_service.generate(
                market_context=market_context,
                market_data=market_data,
                risk_config=risk_config,
            )
        )



        return self.risk_engine.validate(
            trade_plan=trade_plan,
            account_state=account_state,
            risk_config=risk_config,
        )
