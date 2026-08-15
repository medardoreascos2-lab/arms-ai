class StrategyIntelligenceDashboardProviderV1:
    """
    Provee información de inteligencia estratégica
    para Dashboard ARMS AI.
    """


    def __init__(
        self,
        intelligence_orchestrator,
    ):

        self.intelligence_orchestrator = (
            intelligence_orchestrator
        )


    def get_strategy_intelligence(
        self,
        strategies: list[dict],
    ) -> dict:

        result = (
            self.intelligence_orchestrator.analyze(
                strategies
            )
        )


        recommendation = (
            result["recommendation"]
        )


        ranking = []

        for strategy in result["ranking"]:

            ranking.append(
                {
                    "name": strategy["name"],
                    "score": strategy["score"],
                    "status": strategy["status"],
                    "confidence": strategy["confidence"],
                }
            )


        return {
            "recommended_strategy": (
                recommendation["strategy"]
            ),

            "score": (
                recommendation["score"]
            ),

            "status": (
                recommendation["status"]
            ),

            "confidence": (
                recommendation["confidence"]
            ),

            "action": (
                recommendation["action"]
            ),

            "message": (
                recommendation["message"]
            ),

            "ranking": ranking,
        }
