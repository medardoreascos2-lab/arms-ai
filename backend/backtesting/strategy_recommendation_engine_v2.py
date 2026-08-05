
from __future__ import annotations



class StrategyRecommendationEngineV2:
    """
    Motor encargado de recomendar la estrategia
    más compatible con el contexto actual del mercado.
    """



    def recommend(
        self,
        *,
        strategies: list[dict],
        market_context: dict,
    ) -> dict | None:


        if not strategies:

            return None



        regime = market_context.get(
            "regime"
        )


        volatility = market_context.get(
            "volatility"
        )



        candidates = []



        for strategy in strategies:


            conditions = strategy.get(
                "market_conditions",
                [],
            )


            matches = 0



            if regime in conditions:

                matches += 1



            if volatility in conditions:

                matches += 1



            if matches > 0:

                confidence = (
                    matches
                    /
                    2
                    *
                    100
                )


                candidates.append(
                    {
                        **strategy,
                        "confidence": round(
                            confidence,
                            2,
                        ),
                    }
                )



        if not candidates:

            return None



        candidates.sort(
            key=lambda item: (
                item["confidence"],
                item.get(
                    "ranking_score",
                    0,
                ),
            ),
            reverse=True,
        )



        return candidates[0]
