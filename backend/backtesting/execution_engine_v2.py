from __future__ import annotations


class ExecutionEngineV2:
    """
    Motor encargado de preparar la ejecución
    después de una validación de riesgo aprobada.
    """


    def execute(
        self,
        *,
        risk_validation: dict,
        trade_plan: dict,
    ) -> dict:


        if risk_validation.get(
            "status"
        ) != "APPROVED":

            return {
                "status": "BLOCKED",
                "reason": "RISK_NOT_APPROVED",
            }


        direction = (
            risk_validation.get(
                "direction"
            )
            or
            trade_plan.get(
                "direction"
            )
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
            "status": "READY",
            "action": direction,
            "order_type": "MARKET",
            "entry": (
                trade_plan.get(
                    "entry"
                )
            ),
            "stop_loss": (
                trade_plan.get(
                    "stop_loss"
                )
            ),
            "take_profit": (
                trade_plan.get(
                    "take_profit"
                )
            ),
        }
