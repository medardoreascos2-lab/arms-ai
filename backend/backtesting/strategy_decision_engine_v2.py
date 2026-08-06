
from __future__ import annotations



class StrategyDecisionEngineV2:
    """
    Motor encargado de tomar la decisión final
    sobre una estrategia recomendada.

    Evalúa:
    - existencia de estrategia
    - permiso de riesgo
    - tendencia
    - estructura de mercado
    """



    def decide(
        self,
        *,
        strategy: dict | None = None,
        selected_strategy: dict | None = None,
        market_context: dict,
    ) -> dict:



        if strategy is None:
            strategy = selected_strategy


        if strategy is None:

            return {
                "decision": "BLOCK",
                "status": "BLOCKED",
                "reason": "NO_SELECTED_STRATEGY",
                "confidence": 0,
            }



        if market_context.get(
            "risk_allowed"
        ) is False:

            return {
                "decision": "BLOCK",
                "reason": "RISK_NOT_ALLOWED",
                "confidence": (
                    strategy.get(
                        "confidence",
                        0,
                    )
                ),
            }



        trend = market_context.get(
            "trend"
        )


        structure = market_context.get(
            "structure"
        )



        if (
            trend == "BULLISH"
            and structure in (
                "BOS_CONFIRMED",
                "BREAKOUT",
            )
        ):

            return {
                "decision": "EXECUTE",
                "direction": "BUY",
                "strategy_id": (
                    strategy.get(
                        "strategy_id"
                    )
                ),
                "confidence": (
                    strategy.get(
                        "confidence",
                        0,
                    )
                ),
            }



        if (
            trend == "BEARISH"
            and structure in (
                "BOS_CONFIRMED",
                "BREAKOUT",
            )
        ):

            return {
                "decision": "EXECUTE",
                "direction": "SELL",
                "strategy_id": (
                    strategy.get(
                        "strategy_id"
                    )
                ),
                "confidence": (
                    strategy.get(
                        "confidence",
                        0,
                    )
                ),
            }



        return {
            "decision": "BLOCK",
            "reason": "MARKET_NOT_CONFIRMED",
            "confidence": (
                strategy.get(
                    "confidence",
                    0,
                )
            ),
        }
