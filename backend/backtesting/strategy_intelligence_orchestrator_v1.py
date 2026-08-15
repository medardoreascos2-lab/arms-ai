from backend.backtesting.strategy_ranking_engine_v1 import (
    StrategyRankingEngineV1,
)

from backend.backtesting.strategy_recommendation_engine_v1 import (
    StrategyRecommendationEngineV1,
)


class StrategyIntelligenceOrchestratorV1:
    """
    Coordina la inteligencia estratégica
    de ARMS AI.
    """


    def __init__(self):

        self.ranking_engine = (
            StrategyRankingEngineV1()
        )

        self.recommendation_engine = (
            StrategyRecommendationEngineV1()
        )


    def analyze(
        self,
        strategies: list[dict],
    ) -> dict:

        for strategy in strategies:

            self.ranking_engine.add_strategy(
                strategy
            )


        ranked = (
            self.ranking_engine.rank()
        )


        if not ranked:
            return {
                "status": "NO_DATA"
            }


        best_strategy = ranked[0]


        recommendation = (
            self.recommendation_engine.generate(
                {
                    "strategy": best_strategy["name"],
                    "score": best_strategy["score"],
                    "status": best_strategy["status"],
                    "confidence": best_strategy["confidence"],
                }
            )
        )


        return {
            "ranking": ranked,
            "recommendation": recommendation,
        }


    def show(
        self,
        result: dict,
    ):

        print("==============================")
        print(
            "ARMS AI STRATEGY INTELLIGENCE"
        )
        print("==============================")


        print()

        print("RANKING")
        print("------------------------------")

        for item in result["ranking"]:

            print(item)


        print()

        print("FINAL RECOMMENDATION")
        print("------------------------------")

        print(
            result["recommendation"]
        )
