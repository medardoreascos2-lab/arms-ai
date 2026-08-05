
from __future__ import annotations



class ExecutionServiceV2:
    """
    Servicio encargado de coordinar:
    Trade Plan + Risk Validation + Execution Engine.
    """



    def __init__(
        self,
        *,
        trade_plan_service,
        risk_service,
        execution_engine,
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
                risk_service,
                "validate",
                None,
            )
        ):
            raise TypeError(
                "risk_service debe implementar validate()."
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



        self.trade_plan_service = (
            trade_plan_service
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



        if trade_plan.get(
            "status"
        ) != "READY":
            return None



        risk_validation = (
            self.risk_service.validate(
                market_context=market_context,
                market_data=market_data,
                account_state=account_state,
                risk_config=risk_config,
            )
        )



        return self.execution_engine.execute(
            trade_plan=trade_plan,
            risk_validation=risk_validation,
        )
