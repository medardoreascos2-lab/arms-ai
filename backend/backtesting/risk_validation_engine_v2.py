
from __future__ import annotations



class RiskValidationEngineV2:
    """
    Motor encargado de validar si un Trade Plan
    cumple las reglas de riesgo antes de ejecución.
    """



    def validate(
        self,
        *,
        trade_plan: dict,
        account_state: dict,
        risk_config: dict,
    ) -> dict:



        if trade_plan.get(
            "status"
        ) != "READY":

            return {
                "status": "BLOCKED",
                "reason": "INVALID_TRADE_PLAN",
            }



        daily_loss = float(
            account_state.get(
                "daily_loss",
                0,
            )
        )


        max_daily_loss = float(
            account_state.get(
                "max_daily_loss",
                0,
            )
        )



        if (
            daily_loss
            >=
            max_daily_loss
        ):

            return {
                "status": "BLOCKED",
                "reason": "DAILY_LOSS_LIMIT_REACHED",
            }



        risk_amount = float(
            risk_config.get(
                "risk_amount",
                0,
            )
        )



        if risk_amount <= 0:

            return {
                "status": "BLOCKED",
                "reason": "INVALID_RISK_AMOUNT",
            }



        return {
            "status": "APPROVED",
            "risk_amount": risk_amount,
            "direction": (
                trade_plan.get(
                    "direction"
                )
            ),
        }
