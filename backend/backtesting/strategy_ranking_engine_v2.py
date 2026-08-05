
from __future__ import annotations



class StrategyRankingEngineV2:
    """
    Motor de ranking para estrategias certificadas
    de ARMS AI.
    """


    GRADE_SCORES = {
        "A": 100.0,
        "B": 85.0,
        "C": 70.0,
        "D": 50.0,
        "F": 0.0,
    }


    def rank(
        self,
        strategies: list[dict],
    ) -> list[dict]:

        if not strategies:
            return []


        ranked = []


        for strategy in strategies:

            validation_score = float(
                strategy.get(
                    "validation_score",
                    0.0,
                )
            )


            performance_score = float(
                strategy.get(
                    "performance_score",
                    0.0,
                )
            )


            grade = strategy.get(
                "grade",
                "F",
            )


            grade_score = self.GRADE_SCORES.get(
                grade,
                0.0,
            )


            ranking_score = (
                validation_score * 0.4
                +
                performance_score * 0.4
                +
                grade_score * 0.2
            )


            ranked.append(
                {
                    **strategy,
                    "ranking_score": round(
                        ranking_score,
                        2,
                    ),
                }
            )


        ranked.sort(
            key=lambda item: item["ranking_score"],
            reverse=True,
        )


        for index, strategy in enumerate(
            ranked,
            start=1,
        ):

            strategy["rank"] = index


        return ranked
