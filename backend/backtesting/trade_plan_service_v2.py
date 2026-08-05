
from __future__ import annotations



class TradePlanServiceV2:
    """
    Servicio encargado de generar un plan de trading
    usando una decisión validada.
    """



    def __init__(
        self,
        *,
        decision_service,
        trade_plan_engine,
    ):


        if not callable(
            getattr(
                decision_service,
                "decide",
                None,
            )
        ):
            raise TypeError(
                "decision_service debe implementar decide()."
            )



        if not callable(
            getattr(
                trade_plan_engine,
                "generate",
                None,
            )
        ):
            raise TypeError(
                "trade_plan_engine debe implementar generate()."
            )



        self.decision_service = (
            decision_service
        )


        self.trade_plan_engine = (
            trade_plan_engine
        )



    def generate(
        self,
        *,
        market_context: dict,
        market_data: dict,
        risk_config: dict,
    ) -> dict:



        decision = (
            self.decision_service.decide(
                market_context=market_context,
            )
        )



        return self.trade_plan_engine.generate(
            decision=decision,
            market_data=market_data,
            risk_config=risk_config,
        )
