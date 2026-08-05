from __future__ import annotations


class StrategySelectionEngineV2:
    """
    Motor encargado de seleccionar la estrategia
    más adecuada según ranking y contexto del mercado.
    """

    def select(
        self,
        *,
        strategies: list[dict],
        market_context: dict,
    ) -> dict:

        if not strategies:

            return {
                "status": "BLOCKED",
                "reason": "NO_STRATEGIES",
            }


        ranked = sorted(
            strategies,
            key=lambda item: item.get(
                "ranking_score",
                0,
            ),
            reverse=True,
        )


        selected = ranked[0]


        confidence = min(
            float(
                selected.get(
                    "ranking_score",
                    0,
                )
            ),
            100.0,
        )


        return {
            "strategy_id": (
                selected.get(
                    "strategy_id"
                )
            ),

            "strategy_name": (
                selected.get(
                    "strategy_name"
                )
            ),

            "confidence": round(
                confidence,
                2,
            ),

            "market_context": (
                market_context
            ),

            "reason": [
                "Mayor ranking_score disponible",
                "Estrategia certificada por ranking",
            ],
        }
