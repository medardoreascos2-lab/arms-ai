
from __future__ import annotations

from datetime import datetime
import uuid



class TradeLoggerV2:
    """
    Logger encargado de registrar operaciones
    ejecutadas por ARMS AI.
    """



    def log(
        self,
        *,
        execution_result: dict,
        strategy_context: dict,
        risk_validation: dict,
    ) -> dict:



        if execution_result.get(
            "status"
        ) != "EXECUTED":

            return {
                "status": "BLOCKED",
                "reason": "INVALID_EXECUTION",
            }



        trade = {

            "trade_id": str(
                uuid.uuid4()
            ),

            "timestamp": (
                datetime.utcnow()
                .isoformat()
            ),

            "strategy_id": (
                strategy_context.get(
                    "strategy_id"
                )
            ),

            "strategy_name": (
                strategy_context.get(
                    "name"
                )
            ),

            "direction": (
                execution_result.get(
                    "direction"
                )
            ),

            "entry": (
                execution_result.get(
                    "entry"
                )
            ),

            "stop_loss": (
                execution_result.get(
                    "stop_loss"
                )
            ),

            "take_profit": (
                execution_result.get(
                    "take_profit"
                )
            ),

            "risk_amount": (
                risk_validation.get(
                    "risk_amount"
                )
            ),

            "status": "OPEN",

        }



        return {
            "status": "RECORDED",
            "trade": trade,
        }
