
from __future__ import annotations



class TradePlanEngineV2:
    """
    Motor encargado de generar planes de trading
    a partir de una decisión validada.
    """





    def create_plan(
        self,
        *,
        decision: dict,
        market_context: dict,
    ) -> dict:
        """
        Adaptador V2 para crear planes
        directamente desde Strategy Decision.
        """

        result = self.generate(
            decision=decision,
            market_data={
                "entry": market_context.get(
                    "price",
                    0,
                ),
            },
            risk_config={
                "stop_points": 50,
                "risk_reward": 2,
            },
        )


        if result.get(
            "status"
        ) == "READY":

            result["strategy_id"] = (
                decision.get(
                    "strategy_id"
                )
            )


        return result


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
                "reason": "DECISION_NOT_EXECUTABLE",
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
