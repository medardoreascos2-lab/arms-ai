
from __future__ import annotations



class TradePlanEngineV2:
    """
    Motor encargado de generar planes de trading
    a partir de una decisión validada.
    """



    def generate(
        self,
        *,
        decision: dict,
        market_data: dict,
        risk_config: dict,
    ) -> dict:



        if decision.get(
            "decision"
        ) != "EXECUTE":

            return {
                "status": "BLOCKED",
                "reason": "DECISION_NOT_EXECUTE",
            }



        direction = decision.get(
            "direction"
        )


        entry = float(
            market_data.get(
                "entry",
                0,
            )
        )


        stop_points = float(
            risk_config.get(
                "stop_points",
                0,
            )
        )


        risk_reward = float(
            risk_config.get(
                "risk_reward",
                0,
            )
        )



        if direction == "BUY":

            stop_loss = (
                entry
                -
                stop_points
            )

            take_profit = (
                entry
                +
                (
                    stop_points
                    *
                    risk_reward
                )
            )


        elif direction == "SELL":

            stop_loss = (
                entry
                +
                stop_points
            )

            take_profit = (
                entry
                -
                (
                    stop_points
                    *
                    risk_reward
                )
            )


        else:

            return {
                "status": "BLOCKED",
                "reason": "INVALID_DIRECTION",
            }



        return {
            "status": "READY",
            "direction": direction,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "confidence": decision.get(
                "confidence",
                0,
            ),
        }
