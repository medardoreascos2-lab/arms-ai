
from __future__ import annotations



class ExecutionEngineV2:
    """
    Motor encargado de transformar un Trade Plan
    validado en una orden de ejecución simulada.
    """



    def execute(
        self,
        *,
        trade_plan: dict,
        risk_validation: dict,
    ) -> dict:



        if trade_plan.get(
            "status"
        ) != "READY":

            return {
                "status": "BLOCKED",
                "reason": "INVALID_TRADE_PLAN",
            }



        if risk_validation.get(
            "status"
        ) != "APPROVED":

            return {
                "status": "BLOCKED",
                "reason": "RISK_NOT_APPROVED",
            }



        direction = trade_plan.get(
            "direction"
        )


        if direction not in (
            "BUY",
            "SELL",
        ):

            return {
                "status": "BLOCKED",
                "reason": "INVALID_DIRECTION",
            }



        return {
            "status": "EXECUTED",
            "direction": direction,
            "entry": trade_plan.get(
                "entry"
            ),
            "stop_loss": trade_plan.get(
                "stop_loss"
            ),
            "take_profit": trade_plan.get(
                "take_profit"
            ),
        }
