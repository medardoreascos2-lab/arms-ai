class StrategyRecommendationEngineV1:
    """
    Genera recomendación final
    de estrategia ARMS AI.
    """


    def __init__(self):
        self.recommendations = []


    def generate(
        self,
        ranking_result: dict,
    ) -> dict:

        status = ranking_result.get(
            "status",
            "UNKNOWN",
        )

        score = ranking_result.get(
            "score",
            0,
        )


        if status == "APPROVED":

            action = "ACTIVATE_STRATEGY"

            message = (
                "Estrategia aprobada "
                "por rendimiento estadístico."
            )

        elif status == "REVIEW":

            action = "CONTINUE_TESTING"

            message = (
                "Estrategia requiere "
                "más validación."
            )

        else:

            action = "REJECT_STRATEGY"

            message = (
                "Estrategia descartada."
            )


        recommendation = {
            "strategy": ranking_result.get(
                "strategy"
            ),
            "score": score,
            "status": status,
            "confidence": ranking_result.get(
                "confidence"
            ),
            "action": action,
            "message": message,
        }


        self.recommendations.append(
            recommendation
        )


        return recommendation


    def latest(self):

        if not self.recommendations:
            return None

        return self.recommendations[-1]


    def show(
        self,
        recommendation,
    ):

        print("==============================")
        print("ARMS AI STRATEGY RECOMMENDATION")
        print("==============================")


        for key, value in (
            recommendation.items()
        ):
            print(
                f"{key}: {value}"
            )
