class StrategyRankingEngineV1:
    """
    Genera ranking inteligente
    de estrategias ARMS AI.
    """


    def __init__(self):
        self.strategies = []


    def add_strategy(
        self,
        strategy: dict,
    ):

        score = strategy.get(
            "score",
            0,
        )


        if score >= 45:

            status = "APPROVED"

        elif score >= 35:

            status = "REVIEW"

        else:

            status = "REJECTED"


        confidence = (
            "HIGH"
            if score >= 45
            else
            "MEDIUM"
            if score >= 35
            else
            "LOW"
        )


        self.strategies.append(
            {
                **strategy,
                "status": status,
                "confidence": confidence,
            }
        )


    def rank(self):

        return sorted(
            self.strategies,
            key=lambda x: x["score"],
            reverse=True,
        )


    def recommendation(self):

        ranked = self.rank()

        if not ranked:
            return None


        best = ranked[0]


        return {
            "strategy": best["name"],
            "score": best["score"],
            "status": best["status"],
            "confidence": best["confidence"],
            "recommendation": (
                "USE_STRATEGY"
                if best["status"] == "APPROVED"
                else "CONTINUE_TESTING"
            ),
        }


    def show(self):

        print("==============================")
        print("ARMS AI STRATEGY RANKING")
        print("==============================")


        for index, strategy in enumerate(
            self.rank(),
            start=1,
        ):

            print(
                f"#{index}",
                strategy
            )


        print()
        print("RECOMMENDATION")
        print("------------------------------")

        print(
            self.recommendation()
        )
