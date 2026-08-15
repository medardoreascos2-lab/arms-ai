class StrategyAutonomousDecisionEngineV1:
    """
    Motor de decisión autónoma estratégica
    de ARMS AI.
    """


    def __init__(self):

        self.decisions = []


    def decide(
        self,
        strategy: str,
        adaptive_score: float,
        compatibility: str,
        confidence: str,
    ) -> dict:


        reasons = []


        if adaptive_score >= 45:

            reasons.append(
                "Strong statistical performance"
            )

        elif adaptive_score >= 35:

            reasons.append(
                "Acceptable statistical performance"
            )

        else:

            reasons.append(
                "Weak statistical performance"
            )



        if compatibility == "HIGH":

            reasons.append(
                "Market conditions favorable"
            )

        elif compatibility == "MEDIUM":

            reasons.append(
                "Market conditions require monitoring"
            )

        else:

            reasons.append(
                "Market conditions unfavorable"
            )



        if (
            adaptive_score >= 45
            and compatibility == "HIGH"
        ):

            decision = "ACTIVATE"


        elif (
            adaptive_score >= 35
            and compatibility != "LOW"
        ):

            decision = "MONITOR"


        else:

            decision = "DISABLE"



        result = {

            "strategy": strategy,

            "adaptive_score": adaptive_score,

            "market_compatibility": compatibility,

            "confidence": confidence,

            "decision": decision,

            "reasons": reasons,

        }


        self.decisions.append(
            result
        )


        return result



    def latest(self):

        if not self.decisions:

            return None


        return self.decisions[-1]
